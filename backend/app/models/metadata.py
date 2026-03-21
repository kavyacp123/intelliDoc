"""
Schema metadata models.

These dataclasses carry ONLY structural metadata (column names + types).
This is the ONLY information ever sent to the LLM — never raw data values.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ColumnMeta:
    """Single column descriptor."""

    name: str
    dtype: str  # int, float, string, datetime


@dataclass
class TableMetadata:
    """
    Table-level metadata — the safe representation of a dataset.

    This is what gets sent to the LLM adapter — it contains zero
    actual data values, only structural information.
    """

    table_name: str
    columns: List[ColumnMeta] = field(default_factory=list)
    row_count: int = 0
    has_partitions: bool = False
    pre_agg_tables: dict = field(default_factory=dict)
    column_stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "columns": [
                {"name": c.name, "type": c.dtype} for c in self.columns
            ],
            "row_count": self.row_count,
            "has_partitions": self.has_partitions,
            "pre_agg_tables": self.pre_agg_tables,
            "column_stats": self.column_stats,
        }
