"""
Dynamic Hybrid Semantic Service.

Replaces the static YAML semantic config with a runtime schema-aware system.

Features:
  1. Synonym Normalization   — maps user words like "expense" → "cogs", "income" → "revenue"
  2. Dynamic Metric Inference — auto-generates metrics from actual dataset columns at runtime
  3. Redis Caching           — caches inferred semantics per dataset (no recomputation)
  4. Confidence Gating       — only injects semantics if meaningful ones were found

Backward-compatible stubs are included for legacy components (query_builder_service, tasks.py).
"""

import json
import logging
from typing import Dict, List, Optional

from app.models.metadata import TableMetadata
from app.services.cache_service import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 1. SYNONYM MAPPING (DEPRECATED)
#    We now rely on the LLM's intrinsic semantic understanding
#    to dynamically map terms based on the precise dataset schema.
# ─────────────────────────────────────────────
SYNONYMS: Dict[str, str] = {}


def normalize_question(question: str) -> str:
    """
    Apply synonym normalization to a user question.

    (Deprecated: Simply returns the raw question, as the LLM now 
    dynamically maps terms to the injected column schema.)
    """
    normalized = question
    q_lower = question.lower()

    for synonym, canonical in SYNONYMS.items():
        # Word-boundary aware replacement (avoid replacing parts of other words)
        import re
        pattern = r'\b' + re.escape(synonym) + r'\b'
        normalized = re.sub(pattern, canonical, normalized, flags=re.IGNORECASE)

    if normalized != question:
        logger.info("Synonym normalized: '%s' → '%s'", question, normalized)

    return normalized


# ─────────────────────────────────────────────
# 1b. FUZZY COLUMN MATCHING
#     When a user asks about a column that doesn't exist exactly,
#     find the closest real column name from the dataset schema.
# ─────────────────────────────────────────────
def fuzzy_match_column(
    user_term: str,
    actual_columns: list,
    cutoff: float = 0.75,
) -> str | None:
    """
    Find the closest matching column name using difflib.

    Args:
        user_term:      The column name the user/LLM referenced.
        actual_columns: List of real column names from the dataset schema.
        cutoff:         Minimum similarity score (0-1). Default 0.75.

    Returns:
        The best matching column name, or None if no close match found.

    Examples:
        fuzzy_match_column("revenues", ["revenue", "region"]) → "revenue"
        fuzzy_match_column("profitt", ["profit", "product"]) → "profit"
        fuzzy_match_column("xyz", ["revenue", "region"]) → None
    """
    import difflib
    matches = difflib.get_close_matches(
        user_term.lower(),
        [c.lower() for c in actual_columns],
        n=1,
        cutoff=cutoff,
    )
    if not matches:
        return None
    # Return the original casing from actual_columns
    match_lower = matches[0]
    for col in actual_columns:
        if col.lower() == match_lower:
            return col
    return matches[0]


# ─────────────────────────────────────────────
# 2. DYNAMIC METRIC INFERENCE
#    Inspects the actual schema columns at runtime and auto-generates
#    derived metric definitions (e.g. profit = revenue - cogs).
#    Works for ANY dataset — no YAML config required.
# ─────────────────────────────────────────────
def infer_semantics(schema: TableMetadata) -> Dict[str, str]:
    """
    Infer business metrics dynamically from a dataset's schema.

    Checks for common column name patterns and derives metric formulas.
    Returns a dict of { metric_name: sql_expression }.

    Examples:
        {"profit": "revenue - cogs", "total_sales": "SUM(sales)"}
    """
    cols = {c.name.lower() for c in schema.columns}
    semantics: Dict[str, str] = {}

    # ── Profit variants ──
    if "revenue" in cols and "cogs" in cols:
        semantics["profit"] = "revenue - cogs"
    elif "revenue" in cols and "expense" in cols:
        semantics["profit"] = "revenue - expense"
    elif "revenue" in cols and "cost" in cols:
        semantics["profit"] = "revenue - cost"
    elif "income" in cols and "expense" in cols:
        semantics["profit"] = "income - expense"
    elif "sales" in cols and "cogs" in cols:
        semantics["profit"] = "sales - cogs"

    # ── Revenue variants ──
    if "revenue" in cols:
        semantics["total_revenue"] = "SUM(revenue)"
    elif "income" in cols:
        semantics["total_revenue"] = "SUM(income)"
    elif "gross_total" in cols:
        semantics["total_revenue"] = "SUM(gross_total)"
    elif "net_total" in cols:
        semantics["total_revenue"] = "SUM(net_total)"
    elif "sales" in cols:
        semantics["total_revenue"] = "SUM(sales)"
    elif "value" in cols:
        semantics["total_revenue"] = "SUM(value)"

    # ── Cost/Expense variants ──
    if "cogs" in cols:
        semantics["total_cost"] = "SUM(cogs)"
    elif "expense" in cols:
        semantics["total_cost"] = "SUM(expense)"
    elif "cost" in cols:
        semantics["total_cost"] = "SUM(cost)"

    # ── Quantity variants ──
    if "quantity" in cols:
        semantics["total_quantity"] = "SUM(quantity)"
    elif "units" in cols:
        semantics["total_quantity"] = "SUM(units)"
    elif "volume" in cols:
        semantics["total_quantity"] = "SUM(volume)"

    # ── Margin ──
    if "profit" in semantics and "total_revenue" in semantics:
        rev_col = "revenue" if "revenue" in cols else ("income" if "income" in cols else "sales")
        semantics["profit_margin_pct"] = f"(({semantics['profit']}) / NULLIF({rev_col}, 0)) * 100"

    # ── Average order value ──
    if ("revenue" in cols or "sales" in cols) and "quantity" in cols:
        rev_col = "revenue" if "revenue" in cols else "sales"
        semantics["avg_order_value"] = f"SUM({rev_col}) / NULLIF(SUM(quantity), 0)"

    logger.info(
        "Inferred %d semantics for table '%s': %s",
        len(semantics), schema.table_name, list(semantics.keys())
    )
    return semantics


# ─────────────────────────────────────────────
# 3. REDIS CACHE FOR SEMANTICS
#    Caches inferred semantics per dataset_id.
#    Avoids recomputation on every query.
# ─────────────────────────────────────────────
_SEMANTIC_TTL = 60 * 60 * 24  # 24 hours


async def get_cached_semantics(dataset_id: str) -> Optional[Dict[str, str]]:
    """Retrieve semantics from Redis cache for a given dataset."""
    try:
        client = await get_redis()
        raw = await client.get(f"semantics:{dataset_id}")
        if raw:
            logger.info("Semantic cache HIT for dataset %s", dataset_id)
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis semantic GET failed: %s", e)
    return None


async def set_cached_semantics(dataset_id: str, semantics: Dict[str, str]) -> None:
    """Store inferred semantics in Redis cache for a given dataset."""
    try:
        client = await get_redis()
        await client.set(
            f"semantics:{dataset_id}",
            json.dumps(semantics),
            ex=_SEMANTIC_TTL,
        )
        logger.info("Semantic cache SET for dataset %s", dataset_id)
    except Exception as e:
        logger.warning("Redis semantic SET failed: %s", e)


# ─────────────────────────────────────────────
# 4. MAIN ENTRY POINT
#    Called by llm_service to get the semantic context for a dataset.
# ─────────────────────────────────────────────
async def get_semantic_context(
    dataset_id: str,
    schema: TableMetadata,
) -> Dict[str, str]:
    """
    Return inferred semantics for a dataset, using Redis cache when available.

    Args:
        dataset_id: The unique dataset identifier (used as cache key).
        schema: The dataset's TableMetadata.

    Returns:
        Dict of { metric_name: sql_expression }. May be empty if schema
        has no recognizable patterns.
    """
    # Try cache first
    cached = await get_cached_semantics(dataset_id)
    if cached is not None:
        return cached

    # Compute dynamically
    semantics = infer_semantics(schema)

    # Store in Redis for next request
    if semantics:
        await set_cached_semantics(dataset_id, semantics)

    return semantics


def format_semantics_for_prompt(semantics: Dict[str, str]) -> str:
    """
    Format inferred semantics as a readable string for injection into the LLM prompt.

    Returns empty string if no semantics found (confidence gate).
    """
    if not semantics:
        return ""

    lines = ["Inferred business metrics (use these derived formulas when they match the question):"]
    for name, expr in semantics.items():
        lines.append(f"  - {name} = {expr}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# BACKWARD-COMPATIBILITY STUBS
# These are kept so legacy components (query_builder_service, tasks.py)
# continue to import without errors. They use safe hardcoded defaults.
# ─────────────────────────────────────────────

# Hardcoded fallback metrics (used by query_builder_service)
_STATIC_METRICS: Dict[str, str] = {
    "revenue":     "SUM(revenue)",
    "profit":      "SUM(revenue - expense)",
    "sales":       "SUM(revenue)",
    "expense":     "SUM(expense)",
    "quantity":    "SUM(quantity)",
    "order_count": "COUNT(*)",
}

# Hardcoded fallback dimensions (used by query_builder_service)
_STATIC_DIMENSIONS: Dict[str, str] = {
    "region":        "region",
    "country":       "country",
    "product":       "product",
    "category":      "category",
    "customer_type": "customer_type",
    "month":         "DATE_TRUNC('month', date)",
    "quarter":       "DATE_TRUNC('quarter', date)",
    "year":          "DATE_TRUNC('year', date)",
    "day":           "DATE_TRUNC('day', date)",
}

_STATIC_TIME_COLUMN = "date"


def get_metric_expression(metric: str) -> Optional[str]:
    """Legacy: Return SQL expression for a metric name."""
    return _STATIC_METRICS.get(metric)


def get_dimension_expression(dimension: str) -> Optional[str]:
    """Legacy: Return SQL expression for a dimension name."""
    return _STATIC_DIMENSIONS.get(dimension)


def get_time_column() -> str:
    """Legacy: Return the default time column name."""
    return _STATIC_TIME_COLUMN


def get_semantic_summary() -> dict:
    """Legacy: Return available metrics and dimensions as lists."""
    return {
        "available_metrics": list(_STATIC_METRICS.keys()),
        "available_dimensions": list(_STATIC_DIMENSIONS.keys()),
    }

