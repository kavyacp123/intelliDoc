"""
Pydantic schemas for dataset-related API requests and responses.
"""

from typing import List, Optional

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
    """Response for GET /datasets/{id}/schema."""

    dataset_id: str
    table_name: str
    columns: List[ColumnSchema]


class DatasetUploadResponse(BaseModel):
    """Response after successful file upload."""

    dataset_id: str
    table_name: str
    row_count: int
    columns: List[ColumnSchema]
    message: str = "Dataset uploaded successfully"
