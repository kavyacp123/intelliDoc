"""
Dataset API routes.

Endpoints:
  POST /upload                   — Upload a structured dataset (CSV, Excel, JSON)
  GET  /datasets                 — List all datasets for the current user
  GET  /datasets/{id}/schema     — Rich schema discovery: columns, metrics, sample values
"""

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.database import get_connection
from app.core.security import get_current_user
from app.schemas.dataset_schema import (
    ColumnSchema,
    DatasetResponse,
    DatasetSchemaResponse,
    DatasetUploadResponse,
)
from app.services import file_service, schema_service
from app.services.semantic_service import infer_semantics, _STATIC_DIMENSIONS

router = APIRouter(tags=["Datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a dataset",
)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
    """
    Upload a structured dataset file.

    Supported formats: .csv, .xlsx, .xls, .json

    The file is parsed, columns are normalized, a tenant_id column
    is injected, and the data is loaded into DuckDB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Read file bytes
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    try:
        dataset_id, table_name, row_count, metadata = (
            file_service.process_upload(
                file_bytes=file_bytes,
                file_name=file.filename,
                tenant_id=current_user,
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        table_name=table_name,
        row_count=row_count,
        columns=[
            ColumnSchema(name=c.name, type=c.dtype)
            for c in metadata.columns
        ],
    )


@router.get(
    "/datasets",
    response_model=List[DatasetResponse],
    summary="List user datasets",
)
async def list_datasets(current_user: str = Depends(get_current_user)):
    """
    List all datasets owned by the current user.

    Enforces tenant isolation — users can only see their own datasets.
    """
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT dataset_id, table_name, file_name, row_count
        FROM datasets
        WHERE tenant_id = ?
        ORDER BY created_at DESC
        """,
        [current_user],
    ).fetchall()

    return [
        DatasetResponse(
            dataset_id=row[0],
            table_name=row[1],
            file_name=row[2],
            row_count=row[3],
        )
        for row in rows
    ]

@router.delete(
    "/datasets/{dataset_id}",
    summary="Delete a dataset",
)
async def delete_dataset(dataset_id: str, current_user: str = Depends(get_current_user)):
    """Deletes the dataset metadata and all physical DuckDB tables/views for it."""
    conn = get_connection()
    row = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ? AND tenant_id = ?",
        [dataset_id, current_user]
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    table_name = row[0]
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Drop logic: get all matching tables/views
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        for t in tables:
            if t == table_name or t.startswith(f"{table_name}_"):
                try:
                    conn.execute(f'DROP VIEW IF EXISTS "{t}"')
                except: pass
                try:
                    conn.execute(f'DROP TABLE IF EXISTS "{t}"')
                except: pass
                
        conn.execute("DELETE FROM datasets WHERE dataset_id = ?", [dataset_id])
        conn.execute("DELETE FROM dataset_metadata WHERE dataset_id = ?", [dataset_id])
        conn.execute("DELETE FROM chat_history WHERE dataset_id = ?", [dataset_id])
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")
        
    return {"status": "deleted"}


@router.get(
    "/datasets/{dataset_id}/schema",
    response_model=DatasetSchemaResponse,
    summary="Get rich schema info for a dataset",
)
async def get_dataset_schema(
    dataset_id: str,
    current_user: str = Depends(get_current_user),
):
    """
    Discover everything you can query about a dataset:
      - Column names and types
      - Inferred business metrics (profit, total_revenue, etc.)
      - Queryable dimensions (region, month, year, etc.)
      - Sample values for categorical columns

    Use this before querying to understand what questions you can ask.
    """
    conn = get_connection()

    # Verify ownership
    row = conn.execute(
        "SELECT tenant_id, table_name FROM datasets WHERE dataset_id = ?",
        [dataset_id],
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    if row[0] != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you do not own this dataset",
        )

    table_name = row[1]
    metadata = schema_service.get_dataset_schema(dataset_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema metadata not found",
        )

    col_names = [c.name for c in metadata.columns]
    col_types = {c.name: c.dtype for c in metadata.columns}

    # ── Infer business metrics from actual schema ──
    inferred = infer_semantics(metadata)
    inferred_metric_names = list(inferred.keys())

    # ── Find available dimensions (columns that match known dimension keys) ──
    available_dims = [
        dim for dim in _STATIC_DIMENSIONS.keys()
        if dim in col_names
    ]
    # Also add any string/varchar columns that could act as dimensions
    for col in metadata.columns:
        if col.dtype.upper() in ("VARCHAR", "TEXT", "STRING") and col.name not in available_dims:
            available_dims.append(col.name)

    # ── Sample distinct values for categorical columns (max 5 each) ──
    sample_values = {}
    categorical_types = {"varchar", "text", "string"}
    for col in metadata.columns:
        if col.dtype.lower() in categorical_types:
            try:
                rows = conn.execute(
                    f'SELECT DISTINCT "{col.name}" FROM "{table_name}" WHERE "{col.name}" IS NOT NULL LIMIT 5'
                ).fetchall()
                sample_values[col.name] = [r[0] for r in rows]
            except Exception:
                pass  # non-fatal — skip if column query fails

    # ── Build example tip ──
    tip_metric = inferred_metric_names[0] if inferred_metric_names else (col_names[0] if col_names else "revenue")
    tip_dim = available_dims[0] if available_dims else "region"
    tip = f'Try asking: "Show {tip_metric} by {tip_dim}"'

    return DatasetSchemaResponse(
        dataset_id=dataset_id,
        table_name=table_name,
        columns=[ColumnSchema(name=c.name, type=c.dtype) for c in metadata.columns],
        inferred_metrics=inferred_metric_names,
        available_dimensions=available_dims,
        sample_values=sample_values,
        tip=tip,
    )
