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

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "columns": [
                {"name": c.name, "type": c.dtype} for c in self.columns
            ],
        }
