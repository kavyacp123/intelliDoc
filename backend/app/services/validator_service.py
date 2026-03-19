"""
SQL Validator (Service 6 of 8).

Ensures query safety before execution by enforcing strict rules:
  - Only SELECT statements allowed
  - DML/DDL statements (DROP, DELETE, UPDATE, INSERT, ALTER) are blocked
  - Only whitelisted tables and columns are permitted
  - Uses sqlglot for AST-level SQL parsing when available

This is a critical security layer — no query reaches the execution
engine without passing through validation.
"""

import re
from typing import Optional, Set

import sqlglot
from sqlglot import exp


class QueryValidationError(Exception):
    """Raised when a SQL query fails validation."""

    pass


def validate_query(
    sql: str,
    allowed_tables: Optional[Set[str]] = None,
    allowed_columns: Optional[Set[str]] = None,
) -> str:
    """
    Validate a SQL query for safety.

    Checks:
      1. Statement type is SELECT (not DML/DDL)
      2. No dangerous keywords in raw SQL
      3. AST-level validation via sqlglot:
         - Only SELECT expression types
         - All referenced tables are in the allowlist
         - All referenced columns are in the allowlist (if provided)

    Args:
        sql: The SQL query to validate.
        allowed_tables: Set of permitted table names (required).
        allowed_columns: Set of permitted column names (optional).

    Returns:
        The validated SQL string (unchanged if valid).

    Raises:
        QueryValidationError: If any validation check fails.
    """
    if not sql or not sql.strip():
        raise QueryValidationError("Empty query")

    # ── Step 1: Quick keyword blocklist check ──
    _check_dangerous_keywords(sql)

    # ── Step 2: AST-level validation with sqlglot ──
    try:
        parsed = sqlglot.parse(sql, dialect="duckdb")
    except sqlglot.errors.ParseError as e:
        raise QueryValidationError(f"SQL parse error: {e}")

    if not parsed:
        raise QueryValidationError("Failed to parse SQL")

    for statement in parsed:
        # Must be a SELECT statement
        if not isinstance(statement, exp.Select):
            raise QueryValidationError(
                f"Only SELECT statements are allowed, got: "
                f"{type(statement).__name__}"
            )

        # Validate tables
        if allowed_tables:
            _validate_tables(statement, allowed_tables)

        # Validate columns
        if allowed_columns:
            _validate_columns(statement, allowed_columns)

    return sql


def _check_dangerous_keywords(sql: str) -> None:
    """
    Block dangerous SQL keywords using pattern matching.

    This is a first-pass defense — the AST check below is more rigorous.
    """
    dangerous = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bCREATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bMERGE\b",
        r"\bCALL\b",
        r"\bCOPY\b",
    ]
    upper_sql = sql.upper()
    for pattern in dangerous:
        if re.search(pattern, upper_sql):
            keyword = pattern.replace(r"\b", "").strip()
            raise QueryValidationError(
                f"Dangerous keyword detected: {keyword}"
            )


def _validate_tables(
    statement: exp.Select, allowed_tables: Set[str]
) -> None:
    """Ensure all referenced tables are in the allowlist."""
    for table in statement.find_all(exp.Table):
        table_name = table.name
        # Handle quoted identifiers
        if table_name.startswith('"') and table_name.endswith('"'):
            table_name = table_name[1:-1]
        if table_name not in allowed_tables:
            raise QueryValidationError(
                f"Table not allowed: {table_name}. "
                f"Allowed: {allowed_tables}"
            )


def _validate_columns(
    statement: exp.Select, allowed_columns: Set[str]
) -> None:
    """Ensure all referenced columns are in the allowlist."""
    for column in statement.find_all(exp.Column):
        col_name = column.name.lower()
        # Skip star expressions
        if col_name == "*":
            continue
        if col_name not in allowed_columns:
            raise QueryValidationError(
                f"Column not allowed: {col_name}. "
                f"Allowed: {allowed_columns}"
            )
