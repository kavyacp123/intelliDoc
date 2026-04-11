"""
Schema Engine (Service 2 of 8).

Extracts and retrieves schema metadata from the database.
This metadata (column names + types only) is the ONLY information
ever sent to the LLM — raw data values are NEVER exposed.
"""

from typing import List, Optional

from app.core.database import get_connection
from app.models.metadata import ColumnMeta, TableMetadata


def get_dataset_schema(dataset_id: str) -> Optional[TableMetadata]:
    """
    Retrieve the schema metadata for a dataset.

    Args:
        dataset_id: UUID of the dataset.

    Returns:
        TableMetadata with column names and types, or None if not found.
    """
    conn = get_connection()

    # Get table name and row count
    result = conn.execute(
        "SELECT table_name, row_count FROM datasets WHERE dataset_id = ?",
        [dataset_id],
    ).fetchone()

    if result is None:
        return None

    table_name = result[0]
    row_count = result[1] or 0

    columns = conn.execute(
        """
        SELECT column_name, column_type, distinct_count
        FROM dataset_metadata
        WHERE dataset_id = ?
        ORDER BY column_name
        """,
        [dataset_id],
    ).fetchall()

    column_stats = {row[0]: {"distinct": row[2]} for row in columns}

    # Detect partitions and pre-aggregations natively from DuckDB catalog
    all_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    partitions = [t for t in all_tables if t.startswith(f"{table_name}_") and "_agg_" not in t]
    
    pre_agg_tables = {}
    for t in all_tables:
        if t.startswith(f"{table_name}_agg_rev_by_"):
            dim_key = t.split("_by_")[-1] # Extracts "region" or "month"
            pre_agg_tables[dim_key] = t

    return TableMetadata(
        table_name=table_name,
        columns=[ColumnMeta(name=row[0], dtype=row[1]) for row in columns],
        row_count=row_count,
        has_partitions=len(partitions) > 0,
        pre_agg_tables=pre_agg_tables,
        column_stats=column_stats
    )


def get_all_schemas_for_tenant(tenant_id: str) -> List[TableMetadata]:
    """
    Retrieve schema metadata for ALL datasets owned by a tenant.

    Used by the LLM adapter when no specific dataset is targeted.
    """
    conn = get_connection()

    datasets = conn.execute(
        "SELECT dataset_id, table_name, row_count FROM datasets WHERE tenant_id = ?",
        [tenant_id],
    ).fetchall()

    all_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    schemas = []
    for dataset_id, table_name, row_count in datasets:
        row_count = row_count or 0
        columns = conn.execute(
            """
            SELECT column_name, column_type, distinct_count
            FROM dataset_metadata
            WHERE dataset_id = ?
            ORDER BY column_name
            """,
            [dataset_id],
        ).fetchall()

        column_stats = {row[0]: {"distinct": row[2]} for row in columns}

        partitions = [t for t in all_tables if t.startswith(f"{table_name}_") and "_agg_" not in t]
        
        pre_agg_tables = {}
        for t in all_tables:
            if t.startswith(f"{table_name}_agg_rev_by_"):
                dim_key = t.split("_by_")[-1]
                pre_agg_tables[dim_key] = t

        schemas.append(
            TableMetadata(
                table_name=table_name,
                columns=[
                    ColumnMeta(name=r[0], dtype=r[1]) for r in columns
                ],
                row_count=row_count,
                has_partitions=len(partitions) > 0,
                pre_agg_tables=pre_agg_tables,
                column_stats=column_stats
            )
        )

    return schemas


def get_sample_values(
    dataset_id: str,
    limit_per_column: int = 10,
    max_columns: int = 8,
) -> dict[str, list]:
    """
    Retrieve small sample value sets for categorical columns.

    This powers interaction fallbacks such as "did you mean" suggestions for
    likely entity values without exposing large raw datasets.
    """
    metadata = get_dataset_schema(dataset_id)
    if metadata is None:
        return {}

    conn = get_connection()
    sample_values: dict[str, list] = {}
    categorical_types = {"varchar", "text", "string"}

    for col in metadata.columns[:]:
        if len(sample_values) >= max_columns:
            break
        if col.dtype.lower() not in categorical_types:
            continue
        try:
            rows = conn.execute(
                f'SELECT DISTINCT "{col.name}" FROM "{metadata.table_name}" WHERE "{col.name}" IS NOT NULL LIMIT {int(limit_per_column)}'
            ).fetchall()
            values = [r[0] for r in rows if isinstance(r[0], str) and r[0].strip()]
            if values:
                sample_values[col.name] = values
        except Exception:
            continue

    return sample_values
