from app.models.intent import QueryIntent

# ── Keyword sets for deterministic rule matching ──
_ASC_KEYWORDS = {"lowest", "least", "minimum", "smallest", "worst", "bottom", "fewest", "cheapest", "min"}
_DESC_KEYWORDS = {"highest", "most", "maximum", "largest", "best", "top", "greatest", "expensive", "max"}
_AVG_KEYWORDS = {"average", "avg", "mean"}
_COUNT_KEYWORDS = {"count", "how many", "number of"}
_SUM_KEYWORDS = {"total", "sum", "overall"}

def _detect_order(question: str) -> str:
    """Detect ordering intent from natural language keywords."""
    q = question.lower()
    words = set(q.split())
    
    if words & _ASC_KEYWORDS:
        return "asc"
    if words & _DESC_KEYWORDS:
        return "desc"
    return "desc"  # default

def _detect_aggregation(question: str) -> str | None:
    """Detect aggregation type override from natural language."""
    q = question.lower()
    
    if any(kw in q for kw in _AVG_KEYWORDS):
        return "AVG"
    if any(kw in q for kw in _COUNT_KEYWORDS):
        return "COUNT"
    # SUM is the default, no override needed
    return None

def _extract_limit_number(question: str) -> int | None:
    """Extract explicit limit number from phrases like 'top 5', 'bottom 3'."""
    import re
    # Match patterns like "top 5", "bottom 3", "best 10"
    match = re.search(r'\b(?:top|bottom|best|worst|first|last)\s+(\d+)\b', question.lower())
    if match:
        return int(match.group(1))
    return None


def enhance_intent(intent: QueryIntent, question: str, schema: dict) -> QueryIntent:
    """
    Hybrid Rule Engine: applies deterministic python rules to augment
    or override LLM intent. These rules are AUTHORITATIVE — they take
    precedence over LLM output for critical logic like ordering.
    """
    q = question.lower()
    
    # ── Operation Detection (stronger than LLM) ──
    if any(word in q for word in ["top", "best", "highest", "bottom", "worst", "lowest", "least"]):
        intent.operation = "top_n"
        
    if "trend" in q or "over time" in q:
        intent.operation = "trend"
        
    if "compare" in q or " vs " in q:
        intent.operation = "comparison"

    # ── ORDER ENFORCEMENT (critical — never trust LLM for this) ──
    intent.order = _detect_order(question)
        
    # ── Default metric resolution ──
    if not intent.metric:
        for m in ["revenue", "sales", "profit", "quantity", "gross_sales"]:
            if m in schema.get("metrics", []):
                intent.metric = m
                break
                
    # ── Default dimension ──
    if not intent.dimensions and schema.get("dimensions"):
        intent.dimensions = [schema.get("dimensions")[0]]
        
    # ── Limit enforcement ──
    explicit_limit = _extract_limit_number(question)
    if explicit_limit:
        intent.rank = explicit_limit
        intent.limit = explicit_limit
    elif intent.operation == "top_n" and not getattr(intent, 'rank', None):
        intent.rank = 1
        
    # ── Implicit time grain ──
    if not intent.time_grain and intent.operation == "trend":
        intent.time_grain = "month"
        
    if intent.group_by and not intent.time_grain:
        if "year" in intent.group_by:
            intent.time_grain = "year"
        elif "month" in intent.group_by:
            intent.time_grain = "month"

    return intent
