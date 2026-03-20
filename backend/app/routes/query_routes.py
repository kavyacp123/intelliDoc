"""
Query API routes — Direct SQL Generation Pipeline.

The semantic layer (StructuredIntent → QueryBuilder) has been removed.
The LLM now generates SQL directly from the schema metadata.

Flow:
  1. Authenticate & resolve dataset
  2. Extract schema (schema metadata only — never raw data)
  3. LLM generates SQL from schema + question
  4. Validate SQL (SELECT-only safety check)
  5. Inject tenant_id via Query Rewriter
  6. Execute against DuckDB
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
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
    if request.dataset_id:
        conn = get_connection()
        row = conn.execute(
            "SELECT table_name, tenant_id, row_count FROM datasets WHERE dataset_id = ?",
            [request.dataset_id],
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        if row[1] != current_user:
            raise HTTPException(status_code=403, detail="Access denied")
        table_name = row[0]
        row_count = row[2]

    # ── 2. Fetch schema metadata (no raw data) ──
    schemas = []
    if request.dataset_id:
        metadata = schema_service.get_dataset_schema(request.dataset_id)
        schemas = [metadata] if metadata else []
    else:
        schemas = schema_service.get_all_schemas_for_tenant(current_user)

    if not schemas:
        raise HTTPException(status_code=404, detail="No datasets found.")

    if not table_name:
        table_name = schemas[0].table_name

    # ── 3. SQL Cache (Level 1) ──
    cache_key = f"{current_user}:{table_name}:{request.question}"
    sql = await CacheService.get_sql({"cache_key": cache_key})

    if not sql:
        try:
            sql = llm_service.generate_sql(
                question=request.question,
                schemas=schemas,
                table_name=table_name,
            )
            await CacheService.set_sql({"cache_key": cache_key}, sql)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not generate SQL from question: {str(e)}",
            )

    # ── 4. Validate SQL (SELECT-only, whitelisted tables/columns) ──
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

    # ── 5. Inject tenant_id for isolation ──
    safe_sql = rewrite_service.rewrite_query(sql, current_user, table_name)

    chart_hint = llm_service._infer_chart_hint(request.question)

    # ── 6. Result Cache (Level 2) ──
    cached_result = await CacheService.get_result(safe_sql, current_user)
    if cached_result is not None:
        logger.info("Result cache hit for query.")
        return QueryResponse(
            data=cached_result,
            sql=safe_sql,
            chart_hint=chart_hint,
            row_count=len(cached_result),
        )

    # ── Async Routing for Heavy Queries (> 1M rows) ──
    if row_count > 1000000:
        logger.info("Dataset > 1M rows. Dispatching async Celery task.")
        job = run_query_task.delay({"sql": safe_sql}, current_user)
        return AsyncJobResponse(
            job_id=job.id,
            status="processing",
            message="Query is crunching a large dataset in the background.",
        )

    # ── 7. Execute SQL ──
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
