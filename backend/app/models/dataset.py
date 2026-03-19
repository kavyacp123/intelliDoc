"""
Dataset domain model.

Tracks each uploaded dataset and its linkage to a tenant.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Dataset:
    """Internal dataset entity — always scoped to a tenant."""

    dataset_id: str
    tenant_id: str  # foreign key → users.user_id
    table_name: str
    file_name: str
    row_count: int = 0
    created_at: Optional[datetime] = None
