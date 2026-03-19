"""
Query Rewriter (Service 7 of 8).

Enforces security rules automatically by rewriting SQL before execution:
  - Injects tenant_id filter to guarantee data isolation
  - Adds LIMIT clause if missing to prevent full-table scans
  - Ensures every query is scoped to the requesting user's data

This is the final security gate before the Execution Engine.
"""

import re
from typing import Optional

from app.core.config import settings


def rewrite_query(
    sql: str,
    tenant_id: str,
    table_name: str,
    max_limit: Optional[int] = None,
) -> str:
    """
    Rewrite a validated SQL query to enforce tenant isolation and limits.

    Transformations:
      1. Inject WHERE tenant_id = '<tenant_id>' (or AND if WHERE exists)
      2. Add LIMIT clause if missing

    Args:
        sql: The validated SQL query (already passed through validator).
        tenant_id: The current user's tenant ID — injected into WHERE.
        table_name: The table being queried (for targeted rewriting).
        max_limit: Maximum rows to return (default from settings).

    Returns:
        Rewritten SQL string with tenant isolation and limit enforced.
    """
    limit = max_limit or settings.DEFAULT_QUERY_LIMIT

    # ── Step 1: Inject tenant_id filter ──
    sql = _inject_tenant_filter(sql, tenant_id, table_name)

    # ── Step 2: Add LIMIT if missing ──
    sql = _inject_limit(sql, limit)

    return sql


def _inject_tenant_filter(
    sql: str, tenant_id: str, table_name: str
) -> str:
    """
    Inject a tenant_id = '<tenant_id>' condition into the query.

    Strategy:
      - If the query has a WHERE clause, append with AND
      - If no WHERE clause, add one before GROUP BY / ORDER BY / LIMIT
    """
    # Escape tenant_id to prevent injection
    safe_tenant_id = tenant_id.replace("'", "''")
    tenant_condition = f"tenant_id = '{safe_tenant_id}'"

    # Check if WHERE already exists
    where_match = re.search(r"\bWHERE\b", sql, re.IGNORECASE)

    if where_match:
        # Insert tenant condition right after WHERE
        pos = where_match.end()
        sql = sql[:pos] + f" {tenant_condition} AND" + sql[pos:]
    else:
        # Find the right insertion point (before GROUP BY, ORDER BY, LIMIT, or end)
        insertion_patterns = [
            r"\bGROUP\s+BY\b",
            r"\bORDER\s+BY\b",
            r"\bLIMIT\b",
            r"\bHAVING\b",
        ]
        insert_pos = len(sql)
        for pattern in insertion_patterns:
            match = re.search(pattern, sql, re.IGNORECASE)
            if match and match.start() < insert_pos:
                insert_pos = match.start()

        sql = (
            sql[:insert_pos].rstrip()
            + f" WHERE {tenant_condition} "
            + sql[insert_pos:]
        )

    return sql.strip()


def _inject_limit(sql: str, limit: int) -> str:
    """Add a LIMIT clause if the query doesn't already have one."""
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        # Already has a limit — enforce max ceiling
        limit_match = re.search(
            r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE
        )
        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > limit:
                # Cap at the configured maximum
                sql = sql[: limit_match.start(1)] + str(limit) + sql[limit_match.end(1):]
        return sql

    # No LIMIT found — append it
    sql = sql.rstrip().rstrip(";")
    sql += f" LIMIT {limit}"
    return sql
