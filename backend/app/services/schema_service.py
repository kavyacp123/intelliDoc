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

    # Get table name
    result = conn.execute(
        "SELECT table_name FROM datasets WHERE dataset_id = ?",
        [dataset_id],
    ).fetchone()

    if result is None:
        return None

    table_name = result[0]

    # Get column metadata
    columns = conn.execute(
        """
        SELECT column_name, column_type
        FROM dataset_metadata
        WHERE dataset_id = ?
        ORDER BY column_name
        """,
        [dataset_id],
    ).fetchall()

    return TableMetadata(
        table_name=table_name,
        columns=[ColumnMeta(name=row[0], dtype=row[1]) for row in columns],
    )


def get_all_schemas_for_tenant(tenant_id: str) -> List[TableMetadata]:
    """
    Retrieve schema metadata for ALL datasets owned by a tenant.

    Used by the LLM adapter when no specific dataset is targeted.
    """
    conn = get_connection()

    datasets = conn.execute(
        "SELECT dataset_id, table_name FROM datasets WHERE tenant_id = ?",
        [tenant_id],
    ).fetchall()

    schemas = []
    for dataset_id, table_name in datasets:
        columns = conn.execute(
            """
            SELECT column_name, column_type
            FROM dataset_metadata
            WHERE dataset_id = ?
            ORDER BY column_name
            """,
            [dataset_id],
        ).fetchall()

        schemas.append(
            TableMetadata(
                table_name=table_name,
                columns=[
                    ColumnMeta(name=r[0], dtype=r[1]) for r in columns
                ],
            )
        )

    return schemas
