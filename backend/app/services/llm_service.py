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

import json
import re
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from app.core.config import settings

from app.models.metadata import TableMetadata
from app.schemas.query_schema import StructuredIntent
from app.services.semantic_service import get_semantic_summary

def filter_relevant_columns(schemas: List[TableMetadata], question: str) -> List[TableMetadata]:
    """Filter schema to send only relevant columns, reducing LLM payload size and latency."""
    q_lower = question.lower()
    # Keep baseline date/tenant columns + words found in the question
    keep_keywords = {"date", "time", "year", "month", "tenant_id"}
    for word in re.findall(r'\w+', q_lower):
        if len(word) > 2:
            keep_keywords.add(word)
            
    pruned_schemas = []
    for s in schemas:
        kept = []
        for c in s.columns:
            c_name = c.name.lower()
            if any(k in c_name or c_name in k for k in keep_keywords):
                kept.append(c)
        if not kept:
            kept = s.columns[:5] # Fallback if filtering is too aggressive
        pruned_schemas.append(TableMetadata(table_name=s.table_name, columns=kept))
    return pruned_schemas


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

    # ── Intent extraction ──
    print(f"PROVIDER IS {settings.LLM_PROVIDER}")
    if True: # Forced activation of Gemini LLM
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured in .env")
        
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Prune columns to optimize prompt size and response time
        pruned_schemas = filter_relevant_columns(schemas, question)
        
        schema_context = []
        for s in pruned_schemas:
            cols = [f"{c.name} ({c.dtype})" for c in s.columns]
            schema_context.append(f"Table: {s.table_name}, Columns: {', '.join(cols)}")
            
        prompt = f"""
        You are an AI data assistant. Convert the user's natural language question into a structured intent JSON.
        Do not write SQL. Only use the provided metrics and dimensions.
        
        Available Metrics: {available_metrics}
        Available Dimensions: {available_dimensions}
        Schema Context (Use these columns for filters):
        {chr(10).join(schema_context)}
        
        User Question: {question}
        
        Respond ONLY with a valid JSON object matching exactly this schema:
        {{
          "metric": "string (from Available Metrics)",
          "dimension": "string (from Available Dimensions) or null",
          "filters": [
            {{"column": "string", "op": "string (e.g. =, >, <)", "value": "string or number"}}
          ],
          "time_range": "string or null"
        }}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        try:
            data = json.loads(response.text)
            intent = StructuredIntent(
                metric=data.get("metric", available_metrics[0]),
                dimension=data.get("dimension"),
                filters=data.get("filters", []),
                time_range=data.get("time_range")
            )
        except Exception as e:
            raise ValueError(f"Failed to parse Gemini response: {e}")

    else:
        # Fallback to rule-based stub
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
