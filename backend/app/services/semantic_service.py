"""
Dynamic Hybrid Semantic Service.

Replaces the static YAML semantic config with a runtime schema-aware system.

Features:
  1. Synonym Normalization   — maps user words like "expense" → "cogs", "income" → "revenue"
  2. Dynamic Metric Inference — auto-generates metrics from actual dataset columns at runtime
  3. Redis Caching           — caches inferred semantics per dataset (no recomputation)
  4. Confidence Gating       — only injects semantics if meaningful ones were found

This makes the semantic layer work for ANY uploaded dataset automatically.
"""

import json
import logging
from typing import Dict, List, Optional

from app.models.metadata import TableMetadata
from app.services.cache_service import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 1. SYNONYM MAPPING
#    Maps user-facing words → canonical column/concept names.
#    Applied to the question BEFORE it reaches the LLM.
# ─────────────────────────────────────────────
SYNONYMS: Dict[str, str] = {
    # Cost concepts
    "expense":    "cogs",
    "expenses":   "cogs",
    "cost":       "cogs",
    "costs":      "cogs",
    "spending":   "cogs",
    # Revenue concepts
    "income":     "revenue",
    "earnings":   "revenue",
    "turnover":   "revenue",
    "sales":      "revenue",
    "gross":      "revenue",
    # Profit concepts
    "net":        "profit",
    "margin":     "profit",
    "gain":       "profit",
    # Quantity concepts
    "units":      "quantity",
    "items":      "quantity",
    "volume":     "quantity",
    "count":      "quantity",
}


def normalize_question(question: str) -> str:
    """
    Apply synonym normalization to a user question.

    Replaces business synonyms with canonical terms that match
    the dataset columns or inferred metric names.

    Examples:
        "Show me income by region" → "Show me revenue by region"
        "Total expense per category" → "Total cogs per category"
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
    elif "sales" in cols:
        semantics["total_revenue"] = "SUM(sales)"

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
