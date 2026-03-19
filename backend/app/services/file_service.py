"""
File Processing Engine (Service 1 of 8).

Handles:
  - Parsing uploaded files (CSV, Excel, JSON)
  - Normalizing column names
  - Detecting schema automatically
  - Inserting data into DuckDB with tenant_id enforcement
"""

import uuid
from io import BytesIO
from typing import Tuple

import pandas as pd

from app.core.database import get_connection
from app.models.metadata import ColumnMeta, TableMetadata
from app.utils.parser_utils import infer_column_types, normalize_columns


def process_upload(
    file_bytes: bytes,
    file_name: str,
    tenant_id: str,
) -> Tuple[str, str, int, TableMetadata]:
    """
    Process an uploaded file end-to-end.

    Steps:
      1. Detect format from file_name extension
      2. Parse into pandas DataFrame
      3. Normalize column names
      4. Inject tenant_id column
      5. Create DuckDB table
      6. Insert data
      7. Return dataset metadata

    Args:
        file_bytes: Raw file content.
        file_name: Original filename (used for format detection).
        tenant_id: The owning user's ID — injected into every row.

    Returns:
        Tuple of (dataset_id, table_name, row_count, TableMetadata)

    Raises:
        ValueError: If the file format is unsupported or the file is empty.
    """
    # ── Step 1: Parse file into DataFrame ──
    df = _parse_file(file_bytes, file_name)

    if df.empty:
        raise ValueError("Uploaded file contains no data")

    # ── Step 2: Normalize column names ──
    df = normalize_columns(df)

    # ── Step 3: Inject tenant_id ──
    df.insert(0, "tenant_id", tenant_id)

    # ── Step 4: Generate unique identifiers ──
    dataset_id = str(uuid.uuid4())
    table_name = f"dataset_{dataset_id.replace('-', '_')}"

    # ── Step 5: Create table and insert data ──
    conn = get_connection()
    conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM df")

    # ── Step 6: Register in datasets table ──
    conn.execute(
        """
        INSERT INTO datasets (dataset_id, tenant_id, table_name, file_name, row_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        [dataset_id, tenant_id, table_name, file_name, len(df)],
    )

    # ── Step 7: Build metadata ──
    # Exclude tenant_id from the schema sent to users / LLM
    user_df = df.drop(columns=["tenant_id"])
    col_types = infer_column_types(user_df)
    metadata = TableMetadata(
        table_name=table_name,
        columns=[ColumnMeta(name=n, dtype=t) for n, t in col_types],
    )

    # Persist column metadata
    for col_name, col_type in col_types:
        conn.execute(
            """
            INSERT INTO dataset_metadata (dataset_id, column_name, column_type)
            VALUES (?, ?, ?)
            """,
            [dataset_id, col_name, col_type],
        )

    return dataset_id, table_name, len(df), metadata


def _parse_file(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """
    Detect format and parse file bytes into a DataFrame.

    Supported: .csv, .xlsx/.xls, .json
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    buffer = BytesIO(file_bytes)

    if ext == "csv":
        return pd.read_csv(buffer)
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(buffer, engine="openpyxl")
    elif ext == "json":
        return pd.read_json(buffer)
    else:
        raise ValueError(
            f"Unsupported file format: .{ext}. "
            "Accepted formats: .csv, .xlsx, .xls, .json"
        )
