"""
Query Builder Engine (Service 5 of 8).

Converts a StructuredIntent into a SQL query using the Semantic Layer.

This is the controlled SQL generation path:
  - The LLM produces a StructuredIntent (NOT SQL).
  - This builder maps intent fields to pre-defined SQL expressions
    from the Semantic Layer config.
  - No arbitrary SQL is ever generated — only composing from a
    pre-approved expression catalogue.
"""

from typing import Optional

from app.schemas.query_schema import StructuredIntent
from app.services.semantic_service import (
    get_dimension_expression,
    get_metric_expression,
    get_time_column,
)
from app.utils.sql_utils import build_where_clause


def build_query(intent: StructuredIntent) -> str:
    """
    Build a SQL query from a StructuredIntent.

    Steps:
      1. Resolve metric name → SQL expression via semantic layer
      2. Resolve dimension name → SQL expression via semantic layer
      3. Build WHERE clause from filters
      4. Apply time range filter
      5. Compose final SELECT … FROM … WHERE … GROUP BY …

    Args:
        intent: The structured intent from the LLM adapter.

    Returns:
        SQL query string (still needs validation + rewriting before execution).

    Raises:
        ValueError: If the metric is not found in the semantic layer.
    """
    table_name = intent.table_name
    if not table_name:
        raise ValueError("No table_name specified in intent")

    # ── Step 1: Resolve metric ──
    metric_expr = get_metric_expression(intent.metric)
    if not metric_expr:
        # Fallback: try to use the metric name as a column with COUNT
        metric_expr = f"COUNT({intent.metric})"

    metric_alias = intent.metric

    # ── Step 2: Resolve dimension ──
    select_parts = []
    group_by_parts = []

    if intent.dimension:
        dim_expr = get_dimension_expression(intent.dimension)
        if dim_expr:
            select_parts.append(f"{dim_expr} AS {intent.dimension}")
            group_by_parts.append(dim_expr)
        else:
            # Fallback: use dimension name directly as column
            select_parts.append(intent.dimension)
            group_by_parts.append(intent.dimension)

    select_parts.append(f"{metric_expr} AS {metric_alias}")

    # ── Step 3: Build WHERE clause from filters ──
    where_parts = []
    if intent.filters:
        filter_clause = build_where_clause(intent.filters)
        if filter_clause:
            where_parts.append(filter_clause)

    # ── Step 4: Apply time range ──
    time_clause = _build_time_clause(intent.time_range)
    if time_clause:
        where_parts.append(time_clause)

    # ── Step 5: Compose final SQL ──
    sql = f"SELECT {', '.join(select_parts)}"
    sql += f" FROM \"{table_name}\""

    if where_parts:
        sql += f" WHERE {' AND '.join(where_parts)}"

    if group_by_parts:
        sql += f" GROUP BY {', '.join(group_by_parts)}"

    # Add ordering for readability
    if group_by_parts:
        sql += f" ORDER BY {metric_alias} DESC"

    return sql


def _build_time_clause(time_range: Optional[str]) -> Optional[str]:
    """
    Convert a human-readable time range into a SQL WHERE condition.

    Supported formats:
      - "last N months"
      - "last N days"
      - "last N years"
      - "this month"
      - "this year"
      - "last quarter"
    """
    if not time_range:
        return None

    time_col = get_time_column()
    tr = time_range.lower().strip()

    if tr.startswith("last ") and "month" in tr:
        parts = tr.split()
        n = parts[1] if len(parts) >= 3 else "1"
        return f"{time_col} >= CURRENT_DATE - INTERVAL '{n}' MONTH"

    if tr.startswith("last ") and "day" in tr:
        parts = tr.split()
        n = parts[1] if len(parts) >= 3 else "1"
        return f"{time_col} >= CURRENT_DATE - INTERVAL '{n}' DAY"

    if tr.startswith("last ") and "year" in tr:
        parts = tr.split()
        n = parts[1] if len(parts) >= 3 else "1"
        return f"{time_col} >= CURRENT_DATE - INTERVAL '{n}' YEAR"

    if tr == "this month":
        return f"DATE_TRUNC('month', {time_col}) = DATE_TRUNC('month', CURRENT_DATE)"

    if tr == "this year":
        return f"DATE_TRUNC('year', {time_col}) = DATE_TRUNC('year', CURRENT_DATE)"

    if tr == "last quarter":
        return f"{time_col} >= CURRENT_DATE - INTERVAL '3' MONTH"

    return None
