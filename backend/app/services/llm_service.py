"""
LLM Adapter (Service 4 of 8).

Converts a natural language question into a StructuredIntent.

SECURITY CONTRACT:
  - ONLY schema metadata (column names + types) is sent to the LLM.
  - NEVER sends raw data values.
  - NEVER asks the LLM to generate SQL.
  - Output is a StructuredIntent dict, not SQL.

Currently ships with a stub/rule-based implementation.
Swap in a real LLM provider (OpenAI, Gemini, etc.) by implementing
the same interface.
"""

import re
from typing import Any, Dict, List, Optional

from app.models.metadata import TableMetadata
from app.schemas.query_schema import StructuredIntent
from app.services.semantic_service import get_semantic_summary


def generate_intent(
    question: str,
    schemas: List[TableMetadata],
    table_name: Optional[str] = None,
) -> StructuredIntent:
    """
    Convert a natural language question into a StructuredIntent.

    This is the ONLY function that interacts with the LLM (or stub).
    It receives ONLY:
      - The user question (string)
      - Schema metadata (column names + types)
      - Semantic layer summary (metric/dimension names)

    It NEVER receives raw data values.

    Args:
        question: Natural language question from the user.
        schemas: List of table schemas (column names + types only).
        table_name: Optional target table name.

    Returns:
        StructuredIntent with metric, dimension, filters, time_range.
    """
    # Get available metrics and dimensions from semantic layer
    semantic = get_semantic_summary()
    available_metrics = semantic["available_metrics"]
    available_dimensions = semantic["available_dimensions"]

    # ── Stub/Rule-based intent extraction ──
    # In production, replace this block with an actual LLM API call.
    # The prompt would include schema metadata + semantic summary ONLY.
    intent = _rule_based_intent(
        question=question,
        available_metrics=available_metrics,
        available_dimensions=available_dimensions,
        schemas=schemas,
    )

    # Attach target table if specified
    if table_name:
        intent.table_name = table_name
    elif schemas:
        intent.table_name = schemas[0].table_name

    return intent


def _rule_based_intent(
    question: str,
    available_metrics: List[str],
    available_dimensions: List[str],
    schemas: List[TableMetadata],
) -> StructuredIntent:
    """
    Rule-based fallback for intent extraction.

    Matches keywords in the question against available metrics and
    dimensions. Good enough for demo/testing; replace with LLM in prod.
    """
    q = question.lower()

    # ── Match metric ──
    matched_metric = "revenue"  # sensible default
    for metric in available_metrics:
        if metric.lower() in q:
            matched_metric = metric
            break

    # ── Match dimension ──
    matched_dimension = None
    # Check for "by <dimension>" pattern first
    by_match = re.search(r"\bby\s+(\w+)", q)
    if by_match:
        candidate = by_match.group(1).lower()
        for dim in available_dimensions:
            if dim.lower() == candidate or dim.lower().startswith(candidate):
                matched_dimension = dim
                break

    # Fallback: check if any dimension keyword appears anywhere
    if not matched_dimension:
        for dim in available_dimensions:
            if dim.lower() in q:
                matched_dimension = dim
                break

    # ── Match time range ──
    time_range = None
    time_patterns = [
        (r"last\s+(\d+)\s+months?", lambda m: f"last {m.group(1)} months"),
        (r"last\s+(\d+)\s+days?", lambda m: f"last {m.group(1)} days"),
        (r"last\s+(\d+)\s+years?", lambda m: f"last {m.group(1)} years"),
        (r"this\s+month", lambda m: "this month"),
        (r"this\s+year", lambda m: "this year"),
        (r"last\s+quarter", lambda m: "last quarter"),
    ]
    for pattern, extractor in time_patterns:
        match = re.search(pattern, q)
        if match:
            time_range = extractor(match)
            break

    # ── Match filters ──
    filters = _extract_filters(q, schemas)

    # ── Chart hint ──
    chart_hint = _infer_chart_hint(matched_metric, matched_dimension, q)

    return StructuredIntent(
        metric=matched_metric,
        dimension=matched_dimension,
        filters=filters,
        time_range=time_range,
    )


def _extract_filters(
    question: str, schemas: List[TableMetadata]
) -> List[Dict[str, Any]]:
    """
    Extract simple equality filters from the question.

    Looks for patterns like "where region is East" or "for category Electronics".
    """
    filters = []

    # Collect all column names from all schemas
    all_columns = set()
    for schema in schemas:
        for col in schema.columns:
            all_columns.add(col.name)

    # Pattern: "where/for/in <column> is/= <value>"
    pattern = r"(?:where|for|in)\s+(\w+)\s+(?:is|=|equals?)\s+['\"]?(\w+)['\"]?"
    for match in re.finditer(pattern, question):
        col_candidate = match.group(1).lower()
        value = match.group(2)
        if col_candidate in all_columns:
            filters.append(
                {"column": col_candidate, "op": "=", "value": value}
            )

    return filters


def _infer_chart_hint(
    metric: str, dimension: Optional[str], question: str
) -> str:
    """Infer a chart type hint based on the intent."""
    q = question.lower()
    if any(word in q for word in ["trend", "over time", "timeline"]):
        return "line"
    if any(word in q for word in ["distribution", "breakdown", "pie"]):
        return "pie"
    if dimension:
        return "bar"
    return "number"
