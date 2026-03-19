"""
User domain model.

Internal representation of a user — not exposed via API directly.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Internal user entity."""

    user_id: str
    email: str
    password: str  # bcrypt hash — never exposed
    created_at: Optional[datetime] = None
