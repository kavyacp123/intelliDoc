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
from app.services.aggregation_service import run_pre_aggregations


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
    
    # ── Step 2.5: Auto-cast datetime columns to avoid DuckDB VARCHAR errors ──
    for col in df.columns:
        if 'date' in col.lower() or 'time' in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

    # ── Step 3: Infer schema ──tenant_id ──
    df.insert(0, "tenant_id", tenant_id)

    # ── Step 4: Generate unique identifiers ──
    dataset_id = str(uuid.uuid4())
    table_name = f"dataset_{dataset_id.replace('-', '_')}"

    # ── Step 5: Partition and Insert ──
    conn = get_connection()
    
    date_col = None
    for col in df.columns:
        if 'date' in col.lower() or pd.api.types.is_datetime64_any_dtype(df[col]):
            date_col = col
            break

    if date_col:
        df['_month'] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y_%m').fillna('unknown')
        for month, group in df.groupby('_month'):
            part_name = f"{table_name}_{month}"
            group_clean = group.drop(columns=['_month'])
            conn.execute(f'CREATE TABLE IF NOT EXISTS "{part_name}" AS SELECT * FROM group_clean LIMIT 0')
            conn.execute(f'INSERT INTO "{part_name}" SELECT * FROM group_clean')
    else:
        part_name = f"{table_name}_default"
        conn.execute(f'CREATE TABLE "{part_name}" AS SELECT * FROM df')

    # ── Step 5.5: Create logical VIEW over all partitions ──
    _create_logical_view(table_name, conn)

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

    # ── Step 8: Compute Pre-aggregations ──
    run_pre_aggregations(table_name, [c.name for c in metadata.columns])

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


def _create_logical_view(table_name: str, conn) -> None:
    """
    Create (or replace) a logical DuckDB VIEW that unifies all physical
    partition tables under one virtual table name.

    After upload, monthly partitions exist as:
        dataset_xxx_2024_01, dataset_xxx_2024_02, ...

    This function creates:
        CREATE OR REPLACE VIEW dataset_xxx AS
            SELECT * FROM dataset_xxx_2024_01
            UNION ALL
            SELECT * FROM dataset_xxx_2024_02
            ...

    The LLM always generates SQL with the base `table_name`. DuckDB
    transparently routes through this view to the physical partitions.

    Args:
        table_name: The base logical table name (e.g. "dataset_xxx").
        conn: Active DuckDB connection.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Find all partition tables that belong to this dataset
    all_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    partitions = [
        t for t in all_tables
        if t.startswith(f"{table_name}_") and "_agg_" not in t
    ]

    if not partitions:
        logger.warning("No partitions found for %s — view not created", table_name)
        return

    # Build UNION ALL over all partitions
    union_parts = [f'SELECT * FROM "{p}"' for p in sorted(partitions)]
    union_sql = " UNION ALL ".join(union_parts)

    view_sql = f'CREATE OR REPLACE VIEW "{table_name}" AS {union_sql}'

    try:
        conn.execute(view_sql)
        logger.info(
            "Created logical view '%s' over %d partition(s): %s",
            table_name, len(partitions), partitions
        )
    except Exception as e:
        logger.error("Failed to create view for %s: %s", table_name, e)
        raise
