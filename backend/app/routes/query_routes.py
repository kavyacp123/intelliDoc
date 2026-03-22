import logging
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.database import get_connection
from app.core.security import get_current_user
from app.schemas.query_schema import (
    AsyncJobResponse,
    QueryRequest,
    QueryResponse,
    SchemaHintResponse,
)
from app.models.metadata import TableMetadata
from app.models.intent import QueryIntent
from app.services import (
    execution_service,
    rewrite_service,
    schema_service,
    explanation_service,
    validator_service,
    llm_service,
    semantic_service,
)
from app.services.semantic_service import fuzzy_match_column, infer_semantics
from app.services.cache_service import CacheService
from app.worker.tasks import run_query_task
from app.worker.celery_app import celery_app
from app.services.query_planner import QueryPlanner
from app.services.query_guard import enforce_budget
from app.services.insight_service import generate_insights
from app.services.cost_model import update_cost_model
from app.services.cost_estimator import hash_intent
from app.services.intent_processor import enhance_intent
from app.services.intent_validator import validate_intent, IntentValidationError
from app.services.metric_resolver import resolve_metric
from app.services.time_resolver import resolve_time
from app.services.query_builder import build_query
from app.services.table_router import route_query
from app.services.logic_enforcer import enforce_logic

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


# Removed duplicate AsyncJobResponse


@router.post(
    "/query",
    summary="Query your data with natural language",
)
async def query_data(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    # ── 1. Resolve dataset ──
    table_name = None
    row_count = 0
    dataset_id = request.dataset_id

    if dataset_id:
        conn = get_connection()
        row = conn.execute(
            "SELECT table_name, tenant_id, row_count FROM datasets WHERE dataset_id = ?",
            [dataset_id],
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        if row[1] != current_user:
            raise HTTPException(status_code=403, detail="Access denied")
        table_name = row[0]
        row_count = row[2]

    # ── 2. Fetch schema metadata (no raw data) ──
    schemas: list[TableMetadata] = []
    if dataset_id:
        metadata = schema_service.get_dataset_schema(dataset_id)
        schemas = [metadata] if metadata else []
    else:
        schemas = schema_service.get_all_schemas_for_tenant(current_user)

    if not schemas:
        raise HTTPException(status_code=404, detail="No datasets found.")

    if not table_name:
        table_name = schemas[0].table_name

    # ── 3. Synonym Normalization ──
    normalized_question = semantic_service.normalize_question(request.question)

    # ── 4. Fetch Dynamic Semantics (Redis-cached per dataset) ──
    semantics = {}
    if dataset_id and schemas:
        try:
            semantics = await semantic_service.get_semantic_context(
                dataset_id=dataset_id,
                schema=schemas[0],
            )
        except Exception as e:
            logger.warning("Semantic inference failed (non-fatal): %s", e)

    # ── 5. SQL Cache (keyed on normalized question + semantics presence) ──
    cache_key = f"{current_user}:{table_name}:{normalized_question}"
    sql = await CacheService.get_sql({"cache_key": cache_key})

    allowed_columns = {"tenant_id"}
    for s in schemas:
        for c in s.columns:
            allowed_columns.add(c.name)

    execution_plan = {"strategy": "cached_sql", "execution_mode": "sync", "estimated_cost": 0}
    explanation = {"optimization": "Retrieved from parsed semantic SQL cache"}
    insights = []

    if not sql:
        try:
            # ── 5. LLM -> Intent JSON ──
            intent_json = llm_service.generate_intent_json(
                question=normalized_question,
                schemas=schemas,
                table_name=table_name,
                semantics=semantics if semantics else None,
            )

            # ── 5.5 Normalize filters (LLM safety net) ──
            raw_filters = intent_json.get("filters")
            if isinstance(raw_filters, dict):
                # Convert {"product": "Paseo"} → [{"column": "product", "operator": "=", "value": "Paseo"}]
                intent_json["filters"] = [
                    {"column": k, "operator": "=", "value": v}
                    for k, v in raw_filters.items()
                ]
                logger.info("Normalized filters from dict to list: %s", intent_json["filters"])
            elif raw_filters is None:
                intent_json["filters"] = []

            intent_obj = QueryIntent(**intent_json)
            
            # Construct a schema mapping for the Resolvers and Hybrid Engine
            schema_dict = {
                "table_name": table_name,
                "metrics": [c.name for c in schemas[0].columns if c.dtype.lower() in ("int", "float", "double", "bigint", "integer")],
                "dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("string", "varchar", "text")],
                "time_dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("datetime", "date", "timestamp")],
            }
            
            # ── 6. Intent Processor (Hybrid Rules) ──
            intent_obj = enhance_intent(intent_obj, normalized_question, schema_dict)
            
            # ── 7. Resolvers ──
            resolve_metric(intent_obj, schema_dict)
            resolve_time(intent_obj, schema_dict)
            
            # ── 8. Intent Validator ──
            allowed_columns_for_intent = set(allowed_columns)
            if semantics:
                allowed_columns_for_intent.update(semantics.keys())

            try:
                validate_intent(intent_obj, allowed_columns_for_intent)
            except IntentValidationError as e:
                # ── Friendly column-not-found response ──
                suggestion = fuzzy_match_column(e.invalid_column, list(allowed_columns_for_intent)) if e.invalid_column else None
                inferred = infer_semantics(schemas[0]) if schemas else {}
                metric_names = list(inferred.keys())
                available_cols = sorted(allowed_columns_for_intent - {"tenant_id"})
                
                tip = f'Try: "Show {suggestion or available_cols[0]} by region" or call GET /datasets/{{id}}/schema'
                hint = SchemaHintResponse(
                    error=e.message,
                    did_you_mean=suggestion,
                    available_columns=available_cols,
                    inferred_metrics=metric_names,
                    tip=tip,
                )
                return JSONResponse(status_code=400, content=hint.model_dump())

            # ── 9. Query Optimizer Layer (V4 Multi-Plan) ──
            plan = QueryPlanner.plan(intent_obj, schema_dict, schemas[0].to_dict())
            
            # ── 9.5 Budget Enforcer ──
            enforce_budget(plan)
            
            execution_plan = plan
            explanation = explanation_service.generate_explanation(intent_obj, plan)
            
            # ── 10. Query Builder ──
            sql = build_query(intent_obj, plan, current_user)
            
            # ── 11. Schema-Aware Table Router ──
            sql = route_query(sql, plan, table_name)
            
            # ── 12. Post-SQL Logic Enforcer ──
            sql = enforce_logic(sql, intent_obj.order, normalized_question)
            
            await CacheService.set_sql({"cache_key": cache_key}, sql)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error("Query generation failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=422,
                detail=f"Could not generate SQL from question: {str(e)}",
            )

    logger.info("Generated SQL:\n%s", sql)
    
    # ── 6. AST SQL Security Validation ──
    # We still validate the built SQL securely as a final sanity check against injections
    conn = get_connection()
    all_duck_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    try:
        all_duck_views = [r[0] for r in conn.execute("SHOW VIEWS").fetchall()]
    except Exception:
        all_duck_views = []
    all_duck_objects = set(all_duck_tables) | set(all_duck_views)

    allowed_tables = set()
    for s in schemas:
        allowed_tables.add(s.table_name)
        for t in all_duck_objects:
            if t.startswith(f"{s.table_name}_"):
                allowed_tables.add(t)

    try:
        validator_service.validate_query(sql, allowed_tables, allowed_columns)
    except validator_service.QueryValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Query secondary validation failed: {str(e)}"
        )

    # ── 11. Multitenancy isolation is inherently solved by Query Builder ──
    safe_sql = sql
    chart_hint = llm_service._infer_chart_hint(normalized_question)

    # ── 12. Result Cache ──
    cached_result = await CacheService.get_result(safe_sql, current_user)
    if cached_result is not None:
        logger.info("Result cache hit.")
        return QueryResponse(
            data=cached_result,
            sql=safe_sql,
            chart_hint=chart_hint,
            row_count=len(cached_result),
            execution_plan={"strategy": "cache", "execution_mode": "sync", "estimated_cost": 0},
            explanation={"optimization": "Instant read from query cache mapping"},
            insights=[]
        )

    # ── Async Routing for Heavy Queries ──
    if execution_plan.get("execution_mode") == "async" or row_count > 1000000:
        logger.info("Dataset threshold trigger — dispatching async Celery task.")
        job = run_query_task.delay({"sql": safe_sql}, current_user)
        return AsyncJobResponse(
            job_id=job.id,
            status="processing",
            message="Query is crunching a large dataset in the background natively.",
        )

    # ── 9. Execute SQL with Feedback Loop ──
    import time
    start_exec = time.time()
    try:
        data = execution_service.execute_query(safe_sql)
        duration = time.time() - start_exec
        
        # Update self-learning cost model
        try:
            # We need the intent_obj to be available, or we hash the safe_sql
            # For simplicity in V4, we update the model if intent_obj was created
            if 'intent_obj' in locals():
                update_cost_model(hash_intent(locals()['intent_obj']), duration)
        except Exception as feedback_err:
            logger.warning("Feedback loop update failed: %s", feedback_err)

        await CacheService.set_result(safe_sql, current_user, data)
        
        # Generate Insights (V4)
        insights = []
        if 'intent_obj' in locals():
            insights = generate_insights(data, locals()['intent_obj'])

    except execution_service.QueryExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        data=data,
        sql=safe_sql,
        chart_hint=chart_hint,
        row_count=len(data),
        execution_plan=execution_plan,
        explanation=explanation,
        insights=insights
    )


@router.post(
    "/query/suggest",
    summary="Get AI-powered query suggestions for ambiguous questions",
)
async def suggest_queries(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Returns 3 clarified query suggestions based on the user's question
    and the dataset's actual schema.
    """
    from app.services.suggestion_service import generate_suggestions

    dataset_id = request.dataset_id
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required")

    # Get schema for this dataset
    schemas: list[TableMetadata] = []
    metadata = schema_service.get_dataset_schema(dataset_id)
    if metadata:
        schemas = [metadata]

    if not schemas:
        return {"suggestions": []}

    suggestions = generate_suggestions(
        question=request.question,
        schemas=schemas,
    )

    return {"suggestions": suggestions}


@router.post("/query/validate-raw", summary="Test query validation logic directly")
async def validate_raw_query(
    request: QueryRequest,  # reusing this just for convention, we treat question as SQL
    current_user: str = Depends(get_current_user),
):
    """Bypass LLM and directly test the validation engine with raw SQL."""
    conn = get_connection()
    dataset_id = request.dataset_id
    
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id required for raw test")
        
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, current_user],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    table_name = row[0]
    schema = schema_service.get_dataset_schema(dataset_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found for test")
    schemas = [schema]
    
    allowed_tables = {table_name}
    allowed_columns = {"tenant_id"}
    for c in schemas[0].columns:
        allowed_columns.add(c.name)
        
    warnings = []
    try:
        validator_service.validate_query(request.question, allowed_tables, allowed_columns)
        return {"status": "valid", "sql": request.question}
    except validator_service.QueryValidationError as e:
        err_str = str(e)
        if "Column not allowed" in err_str or "column not allowed" in err_str.lower():
            bad_col = None
            import re as _re
            match = _re.search(r"Column not allowed: ([\w]+)", err_str, _re.IGNORECASE)
            if match:
                bad_col = match.group(1)

            available_cols = sorted(allowed_columns - {"tenant_id"})
            suggestion = fuzzy_match_column(bad_col, list(allowed_columns)) if bad_col else None
            
            inferred = infer_semantics(schemas[0])
            metric_names = list(inferred.keys())
            
            hint = SchemaHintResponse(
                error=f"Column '{bad_col}' not found in this dataset." if bad_col else err_str,
                did_you_mean=suggestion,
                available_columns=available_cols,
                inferred_metrics=metric_names,
                tip=f'Try: "Show {suggestion or available_cols[0]} by region" or call GET /datasets/{{id}}/schema'
            )
            return JSONResponse(status_code=400, content=hint.model_dump())
        raise HTTPException(status_code=400, detail=f"Query validation failed: {err_str}")

@router.get("/result/{job_id}")
async def get_async_result(job_id: str, current_user: str = Depends(get_current_user)):
    """Poll for the result of a heavy async query task."""
    result = celery_app.AsyncResult(job_id)
    if not result.ready():
        return {"status": "processing", "job_id": job_id}

    outcome = result.get()
    if outcome.get("status") == "error":
        raise HTTPException(status_code=500, detail=outcome.get("message"))

    return {
        "status": "completed",
        "job_id": job_id,
        "data": outcome.get("data"),
        "sql": outcome.get("sql"),
    }

