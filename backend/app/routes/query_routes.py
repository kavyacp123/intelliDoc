"""
Query API routes with Multi-Layer Caching and Async Job Routing.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.database import get_connection
from app.core.security import get_current_user
from app.schemas.query_schema import QueryRequest, QueryResponse, StructuredIntent
from app.services import (
    execution_service,
    llm_service,
    query_builder_service,
    rewrite_service,
    schema_service,
    validator_service,
)
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
    summary="Query your data with high-performance routing",
)
async def query_data(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
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

    # ── Level 1: Intent Cache ──
    intent_dict = await CacheService.get_intent(current_user, table_name, request.question)
    
    if not intent_dict:
        try:
            intent_obj = llm_service.generate_intent(
                question=request.question,
                schemas=schemas,
                table_name=table_name,
            )
            intent_dict = intent_obj.model_dump()
            await CacheService.set_intent(current_user, table_name, request.question, intent_dict)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not understand the question: {str(e)}")
    else:
        intent_obj = StructuredIntent(**intent_dict)

    # ── Level 2: SQL Cache ──
    sql = await CacheService.get_sql(intent_dict)
    if not sql:
        try:
            sql = query_builder_service.build_query(intent_obj)
            await CacheService.set_sql(intent_dict, sql)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Query build error: {str(e)}")

    # ── Validation ──
    conn = get_connection()
    all_duck_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    
    allowed_tables = set()
    for s in schemas:
        allowed_tables.add(s.table_name)
        for t in all_duck_tables:
            if t.startswith(f"{s.table_name}_"):
                allowed_tables.add(t)
    
    allowed_tables.add("partitioned_data") # allow the union all subquery alias
    
    allowed_columns = set(["tenant_id", "region", "revenue", "month", "sales"])
    for s in schemas:
        for c in s.columns:
            allowed_columns.add(c.name)
    allowed_columns.add(intent_obj.metric)
    if intent_obj.dimension:
        allowed_columns.add(intent_obj.dimension)

    try:
        validator_service.validate_query(sql, allowed_tables, allowed_columns)
    except validator_service.QueryValidationError as e:
        raise HTTPException(status_code=400, detail=f"Query validation failed: {str(e)}")

    safe_sql = rewrite_service.rewrite_query(sql, current_user, table_name)
    chart_hint = llm_service._infer_chart_hint(intent_obj.metric, intent_obj.dimension, request.question)

    # ── Level 3: Result Cache ──
    cached_result = await CacheService.get_result(safe_sql, current_user)
    if cached_result is not None:
        logger.info("Result cache hit for query.")
        return QueryResponse(
            data=cached_result,
            sql=safe_sql,
            intent=intent_obj,
            chart_hint=chart_hint,
            row_count=len(cached_result),
        )

    # ── Async Routing for Heavy Queries ──
    if row_count > 1000000:
        logger.info("Dataset > 1M rows. Dispatching async Celery task.")
        job = run_query_task.delay(intent_dict, current_user)
        return AsyncJobResponse(
            job_id=job.id,
            status="processing",
            message="Query is crunching a large dataset in the background."
        )

    # ── Sync Execution ──
    try:
        data = execution_service.execute_query(safe_sql)
        await CacheService.set_result(safe_sql, current_user, data)
    except execution_service.QueryExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        data=data,
        sql=safe_sql,
        intent=intent_obj,
        chart_hint=chart_hint,
        row_count=len(data),
    )


@router.get("/result/{job_id}")
async def get_async_result(job_id: str, current_user: str = Depends(get_current_user)):
    """Poll for the result of a heavy query task."""
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
        "sql": outcome.get("sql")
    }
