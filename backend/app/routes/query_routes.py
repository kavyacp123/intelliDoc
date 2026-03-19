"""
Query API routes.

Endpoints:
  POST /query — Ask a natural language question about your data

The full pipeline:
  1. User sends NL question
  2. Schema metadata is retrieved (NEVER raw data)
  3. LLM adapter converts question → StructuredIntent
  4. Query builder converts intent → SQL
  5. Validator ensures SQL safety
  6. Rewriter injects tenant isolation + limits
  7. Execution engine runs the query
  8. Results returned as JSON
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_connection
from app.core.security import get_current_user
from app.schemas.query_schema import QueryRequest, QueryResponse
from app.services import (
    execution_service,
    llm_service,
    query_builder_service,
    rewrite_service,
    schema_service,
    validator_service,
)
from app.services.execution_service import QueryExecutionError
from app.services.validator_service import QueryValidationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Query your data with natural language",
)
async def query_data(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Process a natural language query against the user's datasets.

    Security guarantees:
      - Only schema metadata is sent to the LLM (never raw data)
      - LLM produces a StructuredIntent (never SQL)
      - SQL is built from pre-defined semantic layer expressions
      - SQL is validated (SELECT-only, whitelisted tables/columns)
      - SQL is rewritten with tenant_id isolation and LIMIT
    """
    # ── Step 1: Determine target dataset ──
    table_name = None
    if request.dataset_id:
        # Verify ownership
        conn = get_connection()
        row = conn.execute(
            "SELECT table_name, tenant_id FROM datasets WHERE dataset_id = ?",
            [request.dataset_id],
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )
        if row[1] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        table_name = row[0]

    # ── Step 2: Get schema metadata (ONLY metadata, never data) ──
    if request.dataset_id:
        metadata = schema_service.get_dataset_schema(request.dataset_id)
        schemas = [metadata] if metadata else []
    else:
        schemas = schema_service.get_all_schemas_for_tenant(current_user)

    if not schemas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No datasets found. Upload a dataset first.",
        )

    # Use first schema's table if not specified
    if not table_name:
        table_name = schemas[0].table_name

    # ── Step 3: Generate structured intent (LLM adapter) ──
    # SECURITY: Only schema metadata + semantic definitions are sent.
    #           Raw data values NEVER leave the system.
    try:
        intent = llm_service.generate_intent(
            question=request.question,
            schemas=schemas,
            table_name=table_name,
        )
    except Exception as e:
        logger.error("Intent generation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not understand the question: {str(e)}",
        )

    # ── Step 4: Build SQL from intent ──
    try:
        sql = query_builder_service.build_query(intent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query build error: {str(e)}",
        )

    # ── Step 5: Validate SQL ──
    allowed_tables = {s.table_name for s in schemas}
    allowed_columns = set()
    for s in schemas:
        for c in s.columns:
            allowed_columns.add(c.name)
    # Also allow tenant_id and aggregation aliases
    allowed_columns.add("tenant_id")
    allowed_columns.add(intent.metric)
    if intent.dimension:
        allowed_columns.add(intent.dimension)

    try:
        validator_service.validate_query(
            sql=sql,
            allowed_tables=allowed_tables,
            allowed_columns=allowed_columns,
        )
    except QueryValidationError as e:
        logger.warning("Query validation failed: %s | SQL: %s", str(e), sql)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query validation failed: {str(e)}",
        )

    # ── Step 6: Rewrite SQL (tenant isolation + limit) ──
    rewritten_sql = rewrite_service.rewrite_query(
        sql=sql,
        tenant_id=current_user,
        table_name=table_name,
    )

    # ── Step 7: Execute ──
    try:
        data = execution_service.execute_query(rewritten_sql)
    except QueryExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}",
        )

    # ── Step 8: Determine chart hint ──
    chart_hint = llm_service._infer_chart_hint(
        intent.metric, intent.dimension, request.question
    )

    return QueryResponse(
        data=data,
        sql=rewritten_sql,
        intent=intent,
        chart_hint=chart_hint,
        row_count=len(data),
    )
