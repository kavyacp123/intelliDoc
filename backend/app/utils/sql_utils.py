"""
SQL utility helpers.

Functions for sanitizing identifiers, building WHERE clauses,
and other SQL construction primitives.
"""

import re
from typing import Any, Dict, List, Optional


def sanitize_identifier(name: str) -> str:
    """
    Make a string safe for use as a SQL identifier.

    Rules:
      - Lowercase
      - Replace spaces / special chars with underscores
      - Strip leading/trailing underscores
      - Must start with a letter
    """
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)  # collapse multiple underscores
    name = name.strip("_")
    if not name or not name[0].isalpha():
        name = "col_" + name
    return name


def build_where_clause(
    filters: List[Dict[str, Any]],
    allowed_columns: Optional[set] = None,
) -> str:
    """
    Build a WHERE clause from a list of filter dicts.

    Each filter: {"column": str, "op": str, "value": Any}
    Supported ops: =, !=, >, <, >=, <=, LIKE, IN

    Returns an empty string if no valid filters.
    Raises ValueError for disallowed columns or operators.
    """
    if not filters:
        return ""

    allowed_ops = {"=", "!=", ">", "<", ">=", "<=", "LIKE", "IN"}
    clauses = []

    for f in filters:
        col = sanitize_identifier(f["column"])
        op = f.get("op", "=").upper()
        value = f["value"]

        # Validate operator
        if op not in allowed_ops:
            raise ValueError(f"Disallowed operator: {op}")

        # Validate column if allowlist provided
        if allowed_columns and col not in allowed_columns:
            raise ValueError(f"Column not allowed in filter: {col}")

        # Build the clause
        if op == "IN" and isinstance(value, list):
            escaped = ", ".join(f"'{_escape_value(v)}'" for v in value)
            clauses.append(f"{col} IN ({escaped})")
        elif isinstance(value, str):
            clauses.append(f"{col} {op} '{_escape_value(value)}'")
        else:
            clauses.append(f"{col} {op} {value}")

    return " AND ".join(clauses)


def _escape_value(value: str) -> str:
    """Basic SQL injection prevention for string values."""
    return value.replace("'", "''").replace(";", "").replace("--", "")
