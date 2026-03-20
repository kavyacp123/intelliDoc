"""
Query API routes — Hybrid Semantic SQL Generation Pipeline.

Full flow:
  1. Authenticate & resolve dataset
  2. Fetch schema metadata (never raw data)
  3. Normalize question with synonym mapping
  4. Fetch/compute dynamic semantics (Redis-cached per dataset)
  5. LLM generates SQL using schema + semantics
  6. Validate SQL (SELECT-only, whitelisted columns/tables)
  7. Inject tenant_id via Query Rewriter (multi-tenancy isolation)
  8. Execute against DuckDB & cache result
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import get_connection
from app.core.security import get_current_user
from app.schemas.query_schema import QueryRequest, QueryResponse
from app.services import (
    execution_service,
    rewrite_service,
    schema_service,
    validator_service,
)
from app.services import llm_service
from app.services import semantic_service
from app.services.cache_service import CacheService
from app.worker.tasks import run_query_task
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


class AsyncJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


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
    schemas = []
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

    if not sql:
        try:
            sql = llm_service.generate_sql(
                question=normalized_question,
                schemas=schemas,
                table_name=table_name,
                semantics=semantics if semantics else None,
            )
            await CacheService.set_sql({"cache_key": cache_key}, sql)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not generate SQL from question: {str(e)}",
            )

    logger.info("Generated SQL:\n%s", sql)

    # ── 6. Validate SQL (SELECT-only, whitelisted tables/columns) ──
    conn = get_connection()
    all_duck_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    allowed_tables = set()
    for s in schemas:
        allowed_tables.add(s.table_name)
        for t in all_duck_tables:
            if t.startswith(f"{s.table_name}_"):
                allowed_tables.add(t)

    allowed_columns = {"tenant_id"}
    for s in schemas:
        for c in s.columns:
            allowed_columns.add(c.name)

    try:
        validator_service.validate_query(sql, allowed_tables, allowed_columns)
    except validator_service.QueryValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Query validation failed: {str(e)}"
        )

    # ── 7. Inject tenant_id for multi-tenant isolation ──
    safe_sql = rewrite_service.rewrite_query(sql, current_user, table_name)
    chart_hint = llm_service._infer_chart_hint(normalized_question)

    # ── 8. Result Cache ──
    cached_result = await CacheService.get_result(safe_sql, current_user)
    if cached_result is not None:
        logger.info("Result cache hit.")
        return QueryResponse(
            data=cached_result,
            sql=safe_sql,
            chart_hint=chart_hint,
            row_count=len(cached_result),
        )

    # ── Async Routing for Heavy Queries (> 1M rows) ──
    if row_count > 1000000:
        logger.info("Dataset > 1M rows — dispatching async Celery task.")
        job = run_query_task.delay({"sql": safe_sql}, current_user)
        return AsyncJobResponse(
            job_id=job.id,
            status="processing",
            message="Query is crunching a large dataset in the background.",
        )

    # ── 9. Execute SQL ──
    try:
        data = execution_service.execute_query(safe_sql)
        await CacheService.set_result(safe_sql, current_user, data)
    except execution_service.QueryExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        data=data,
        sql=safe_sql,
        chart_hint=chart_hint,
        row_count=len(data),
    )


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
