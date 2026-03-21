"""
Pydantic schemas for dataset-related API requests and responses.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    """Single column metadata in a dataset."""

    name: str
    type: str


class DatasetResponse(BaseModel):
    """Response when listing datasets."""

    dataset_id: str
    table_name: str
    file_name: str
    row_count: int


class DatasetSchemaResponse(BaseModel):
    """Response for GET /datasets/{id}/schema — rich schema discovery."""

    dataset_id: str
    table_name: str
    columns: List[ColumnSchema]
    # Inferred business metrics (e.g. "profit", "total_revenue")
    inferred_metrics: List[str] = []
    # Available dimensions for grouping (e.g. "region", "month")
    available_dimensions: List[str] = []
    # Sample distinct values per categorical column (max 5 each)
    sample_values: Dict[str, List[Any]] = {}
    # Tip message for the user
    tip: str = ""


class DatasetUploadResponse(BaseModel):
    """Response after successful file upload."""

    dataset_id: str
    table_name: str
    row_count: int
    columns: List[ColumnSchema]
    message: str = "Dataset uploaded successfully"
