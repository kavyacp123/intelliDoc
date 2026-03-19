"""
Dataset API routes.

Endpoints:
  POST /upload             — Upload a structured dataset (CSV, Excel, JSON)
  GET  /datasets           — List all datasets for the current user
  GET  /datasets/{id}/schema — Get the schema metadata for a dataset
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


@router.get(
    "/datasets/{dataset_id}/schema",
    response_model=DatasetSchemaResponse,
    summary="Get dataset schema",
)
async def get_dataset_schema(
    dataset_id: str,
    current_user: str = Depends(get_current_user),
):
    """
    Retrieve the schema metadata for a specific dataset.

    Returns column names and types ONLY — never raw data.
    Enforces tenant isolation.
    """
    conn = get_connection()

    # Verify ownership
    row = conn.execute(
        "SELECT tenant_id FROM datasets WHERE dataset_id = ?",
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

    metadata = schema_service.get_dataset_schema(dataset_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema metadata not found",
        )

    return DatasetSchemaResponse(
        dataset_id=dataset_id,
        table_name=metadata.table_name,
        columns=[
            ColumnSchema(name=c.name, type=c.dtype) for c in metadata.columns
        ],
    )
