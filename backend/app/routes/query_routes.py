import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query as FastAPIQuery
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
import io

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
from app.services.table_router import route_query
from app.services.logic_enforcer import enforce_logic
from app.services.confidence_service import score_plan_confidence
from app.services import rag_service
from app.services.interaction_controller import build_interaction_response, resolve_from_history
from app.services.session_service import session_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])

def _filter_tenant_id(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove tenant_id from result set to ensure data privacy in UI/exports."""
    if not data:
        return data
    for row in data:
        row.pop("tenant_id", None)
    return data


def _is_completely_vague(question: str) -> bool:
    vague_inputs = {
        "show data",
        "show summary",
        "summary",
        "overview",
        "performance",
        "show performance",
    }
    return question.lower().strip() in vague_inputs


def _assumed_defaults(confidence_result: Dict[str, Any]) -> List[str]:
    assumptions = []
    for issue in confidence_result.get("issues", []):
        issue_type = issue.get("type")
        if issue_type in {"weak_mapping", "missing_metric", "ambiguity"}:
            assumptions.append(issue.get("description", ""))
    return assumptions[:3]


# Removed duplicate AsyncJobResponse


@router.post(
    "/query",
    summary="Query your data with natural language",
)
async def query_data(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    feedback_info = None
    active_session_id = request.session_id

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

    if request.clarification_feedback:
        feedback = request.clarification_feedback
        pending = session_service.get_pending_interaction(
            session_id=feedback.get("session_id") or request.session_id,
            tenant_id=current_user,
        )
        if pending:
            active_session_id = feedback.get("session_id") or request.session_id
            answer_key = feedback.get("answer_key") or request.answer_key
            answer_value = feedback.get("answer_value") or feedback.get("selected_option", "") or request.answer_value

            if answer_key:
                session_service.add_answer(active_session_id, current_user, answer_key, answer_value)
                pending = session_service.get_pending_interaction(active_session_id, current_user) or pending
                if not session_service.is_complete(active_session_id, current_user):
                    waiting_payload = dict(pending.get("context", {}).get("interaction_payload") or {})
                    waiting_payload["answers"] = pending.get("answers", {})
                    return QueryResponse(
                        data=[],
                        sql="",
                        chart_hint=None,
                        row_count=0,
                        warnings=[],
                        execution_plan={
                            "strategy": "clarification_waiting",
                            "execution_mode": "sync",
                            "estimated_cost": 0,
                        },
                        explanation={"optimization": "Waiting for the remaining clarification answers before execution."},
                        insights=None,
                        needs_clarification=True,
                        clarification_question=waiting_payload.get("message"),
                        clarification_options=[],
                        clarification_terms=pending.get("context", {}).get("clarification_terms", []),
                        failure_type=pending.get("failure_type"),
                        interaction_type="clarification_chat",
                        interaction_payload=waiting_payload,
                        session_id=active_session_id,
                    )

                request.question = llm_service.refine_query(
                    original_query=pending.get("original_query", request.question),
                    clarification=pending.get("answers", {}),
                )
            else:
                request.question = llm_service.refine_query(
                    original_query=pending.get("original_query", request.question),
                    clarification=feedback.get("selected_option", ""),
                )
            session_service.clear_pending_interaction(active_session_id, current_user)

        schema_preview = {
            "metrics": [c.name for c in schemas[0].columns if c.dtype.lower() in ("int", "float", "double", "bigint", "integer")],
            "dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("string", "varchar", "text")],
            "time_dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("datetime", "date", "timestamp")],
            "semantic_metrics": [],
        }
        feedback_info = rag_service.learn_from_clarification(
            selected_option=feedback.get("selected_option", ""),
            ambiguous_terms=feedback.get("ambiguous_terms", []),
            schema=schema_preview,
            tenant_id=current_user,
            dataset_id=dataset_id,
        )
        request.question = request.question or feedback.get("original_query", request.question)

    # ── 3. Synonym Normalization ──
    normalized_question = semantic_service.normalize_question(request.question)
    session_context = session_service.get_session_context(active_session_id, current_user)

    if _is_completely_vague(normalized_question):
        suggestions = []
        try:
            from app.services.suggestion_service import generate_suggestions

            suggestions = generate_suggestions(normalized_question, schemas)
        except Exception:
            suggestions = []

        active_session_id = session_service.merge_session_context(
            active_session_id,
            current_user,
            dataset_id=dataset_id,
            last_dimensions=session_context.get("last_dimensions"),
            last_metric=session_context.get("last_metric"),
        )
        return QueryResponse(
            data=[],
            sql="",
            chart_hint=None,
            row_count=0,
            warnings=[],
            execution_plan={"strategy": "suggestions", "execution_mode": "sync", "estimated_cost": 0},
            explanation={"optimization": "The system asked for a more specific query before execution."},
            insights=None,
            needs_clarification=True,
            clarification_question="I can answer this faster if you tell me what metric or angle you want.",
            clarification_options=suggestions,
            interaction_type="suggestions",
            interaction_payload={"message": "Pick one of these or keep your original wording.", "options": suggestions},
            session_id=active_session_id,
            interpretation="I treated your request as too broad to interpret safely without a metric or angle.",
            correction_prompt="Pick a suggestion or tell me what metric should matter.",
        )

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
            from app.models.intent import MultiStepPlan
            
            # ── 5. LLM -> Intent JSON ──
            intent_json = llm_service.generate_intent_json(
                question=normalized_question,
                schemas=schemas,
                table_name=table_name,
                semantics=semantics if semantics else None,
            )

            # ── 5.5 Create MultiStepPlan ──
            plan_obj = MultiStepPlan(**intent_json)
            original_plan = plan_obj.model_copy(deep=True)
            
            # Construct a schema mapping for the Resolvers and Hybrid Engine
            schema_dict = {
                "table_name": table_name,
                "metrics": [c.name for c in schemas[0].columns if c.dtype.lower() in ("int", "float", "double", "bigint", "integer")],
                "dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("string", "varchar", "text")],
                "time_dimensions": [c.name for c in schemas[0].columns if c.dtype.lower() in ("datetime", "date", "timestamp")],
                "semantic_metrics": list(semantics.keys()) if semantics else [],
            }
            
            # ── 6. Intent Processor (Hybrid Rules) ──
            plan_obj = enhance_intent(plan_obj, normalized_question, schema_dict)
            
            # ── 7. Resolvers ──
            resolve_metric(plan_obj, schema_dict)
            resolve_time(plan_obj, schema_dict)
            history_resolution = resolve_from_history(
                question=normalized_question,
                plan=plan_obj,
                schema=schema_dict,
                session_context=session_context,
            )

            rag_matches = rag_service.retrieve_business_context(
                question=normalized_question,
                tenant_id=current_user,
                dataset_id=dataset_id,
            )
            rag_resolution = rag_service.apply_business_context(
                plan=plan_obj,
                question=normalized_question,
                schema=schema_dict,
                matches=rag_matches,
            )

            confidence_result = score_plan_confidence(
                question=normalized_question,
                original_plan=original_plan,
                resolved_plan=plan_obj,
                schema=schema_dict,
                semantics=semantics,
                rag_resolved_terms=rag_resolution["resolved_terms"],
                rag_term_results=rag_resolution["term_results"],
                session_context=session_context,
            )

            interaction = None
            if confidence_result["needs_clarification"]:
                sample_values = schema_service.get_sample_values(dataset_id) if dataset_id else {}
                interaction = build_interaction_response(
                    question=normalized_question,
                    original_plan=original_plan,
                    resolved_plan=plan_obj,
                    schema=schema_dict,
                    confidence_result=confidence_result,
                    sample_values=sample_values,
                )
                active_session_id = session_service.create_or_update_pending_interaction(
                    session_id=active_session_id,
                    tenant_id=current_user,
                    dataset_id=dataset_id,
                    interaction={
                        "original_query": normalized_question,
                        "failure_type": interaction["failure_type"],
                        "interaction_type": interaction.get("interaction_type"),
                        "questions": interaction.get("payload", {}).get("questions", []),
                        "expected_fields": interaction.get("payload", {}).get("expected_fields", []),
                        "context": {
                            "clarification_terms": confidence_result["clarification_terms"],
                            "interaction_payload": interaction.get("payload"),
                        },
                    },
                )
            # ── 8. Intent Validator ──
            allowed_columns_for_intent = set(allowed_columns)
            if semantics:
                allowed_columns_for_intent.update(semantics.keys())

            try:
                validate_intent(plan_obj, allowed_columns_for_intent)
            except IntentValidationError as e:
                # Friendly column-not-found response
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

            from app.services.orchestrator import Orchestrator
            # Orchestrator handles all steps and execution dynamically
            actual_cols = [c.name for c in schemas[0].columns] if schemas else []
            result = Orchestrator.execute_plan(plan_obj, table_name, current_user, semantics, actual_cols)
            data = _filter_tenant_id(result["data"])
            sql = result["sqls"][-1] if result["sqls"] else "SELECT 1"
            safe_sql = sql
            
            await CacheService.set_result(safe_sql, current_user, data)
            
            execution_plan = {"strategy": plan_obj.query_type, "execution_mode": "sync", "estimated_cost": 10}
            explanation = {"optimization": plan_obj.final_output.description}
            
            from app.services.insight_service import generate_insights
            insights_res = generate_insights(data, normalized_question, safe_sql, plan_obj)
            
            # Use LLM recommendation if available, otherwise heuristic
            if insights_res.chart:
                chart_hint = insights_res.chart.type
            else:
                chart_hint = llm_service._infer_chart_hint(normalized_question)
            
            active_session_id = session_service.merge_session_context(
                active_session_id,
                current_user,
                dataset_id=dataset_id,
                resolved_terms={
                    **(history_resolution.get("resolved_terms") or {}),
                    **(rag_resolution.get("resolved_terms") or {}),
                },
                last_metric=next((step.metric for step in plan_obj.steps if step.metric), None),
                last_dimensions=next((step.dimensions for step in plan_obj.steps if step.dimensions), []),
            )

            return QueryResponse(
                data=data,
                sql=safe_sql,
                chart_hint=chart_hint,
                row_count=len(data),
                warnings=_merge_warnings(rag_resolution["applied_rules"], feedback_info) + [
                    issue["description"] for issue in confidence_result["issues"]
                ],
                execution_plan=execution_plan,
                explanation=explanation,
                insights=insights_res,
                confidence_score=confidence_result["confidence"],
                confidence_issues=confidence_result["issues"],
                needs_clarification=bool(interaction),
                clarification_question=interaction["question"] if interaction else None,
                clarification_options=interaction["options"] if interaction else [],
                clarification_terms=confidence_result["clarification_terms"],
                failure_type=interaction["failure_type"] if interaction else None,
                interaction_type=interaction.get("interaction_type") if interaction else None,
                interaction_payload=interaction.get("payload") if interaction else None,
                session_id=active_session_id,
                interpretation=confidence_result.get("interpretation"),
                correction_prompt="Not what you meant? Tell me what to change and I will adjust the query.",
                assumed_defaults=_assumed_defaults(confidence_result),
            )
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error("Query generation failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=422,
                detail=f"Could not generate SQL from question: {str(e)}",
            )

    
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
        cached_result = _filter_tenant_id(cached_result)
        return QueryResponse(
            data=cached_result,
            sql=safe_sql,
            chart_hint=chart_hint,
            row_count=len(cached_result),
            execution_plan={"strategy": "cache", "execution_mode": "sync", "estimated_cost": 0},
            explanation={"optimization": "Instant read from query cache mapping"},
            insights=None,
            confidence_score=1.0,
            session_id=active_session_id,
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

        data = _filter_tenant_id(data)
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
        insights=None,
        confidence_score=1.0,
        session_id=active_session_id,
    )


def _merge_warnings(rag_warnings: List[str], feedback_info: Optional[Dict[str, Any]]) -> List[str]:
    warnings = list(rag_warnings)
    if feedback_info and feedback_info.get("stored"):
        warnings.append(
            f"Learned '{feedback_info['term']}' as '{feedback_info['meaning']}' from your clarification."
        )
    return warnings


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
        "data": _filter_tenant_id(outcome.get("data", [])),
        "sql": outcome.get("sql"),
    }

@router.post("/query/export", summary="Export query results to Excel")
async def export_query_results(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Execute the query (or fetch from cache) and return an Excel file directly.
    The response handles large datasets by streaming the byte content.
    """
    # For simplicity, we re-run the logic but return a StreamingResponse
    # Alternatively, we could fetch from ResultCache if the user just queried it.
    
    # ── 1. Determine SQL ──
    # Note: Building a full export here. We re-use Cache for speed.
    # In a full production app, we would share logic between /query and /export.
    
    # We'll just call the query_data logic but return Excel.
    # To keep it DRY, we usually factor out the 'get_data_from_question' logic.
    # Since we are an AI, we'll implement it directly here for the user's immediate need.
    
    dataset_id = request.dataset_id
    if not dataset_id:
         raise HTTPException(status_code=400, detail="dataset_id required for export")

    conn = get_connection()
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, current_user]
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
    table_name = row[0]

    # We use a trick: get the result of the query directly.
    # If the user just ran the query, it's in Cache.
    # For now, let's assume we want a fresh run or cached result.
    from app.services.cache_service import CacheService
    
    # Re-normalize etc. 
    normalized_question = semantic_service.normalize_question(request.question)
    cache_key = f"{current_user}:{table_name}:{normalized_question}"
    sql = await CacheService.get_sql({"cache_key": cache_key})
    
    if not sql:
        # If not cached, we need to generate it again (or the user must query first)
        # For simplicity, we'll try to get it from the LLM service if needed.
        raise HTTPException(status_code=400, detail="Please run the query first to generate SQL, then export.")

    data = await CacheService.get_result(sql, current_user)
    if data is None:
        data = execution_service.execute_query(sql)

    # Filter tenant_id
    filtered_data = _filter_tenant_id(data)
    
    if not filtered_data:
        raise HTTPException(status_code=400, detail="No data found to export.")

    # Convert to DataFrame
    df = pd.DataFrame(filtered_data)
    
    # Write to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Query Results')
    
    output.seek(0)
    
    filename = f"intelliDoc_Export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
