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


from app.models.intent import MultiStepPlan, StepIntent

def enhance_intent(plan: MultiStepPlan, question: str, schema: dict) -> MultiStepPlan:
    """
    Hybrid Rule Engine: applies deterministic python rules to augment
    or override LLM intent. Applied to each step.
    """
    q = question.lower()
    
    for step in plan.steps:
        # ── Operation Detection (stronger than LLM) ──
        if any(word in q for word in ["top", "best", "highest", "bottom", "worst", "lowest", "least"]):
            if step.intent_type != "row_level":
                step.intent_type = "top_n"
            
        if "trend" in q or "over time" in q:
            if step.intent_type != "row_level":
                step.intent_type = "trend"
            
        if "compare" in q or " vs " in q:
            if step.intent_type != "row_level":
                step.intent_type = "comparison"

        # ── ORDER ENFORCEMENT (critical) ──
        if step.order is None or step.order == "NONE":
             if step.intent_type == "top_n":
                 step.order = _detect_order(question)
                 # Re-apply for edge case overrides
                 if any(kw in q for kw in _ASC_KEYWORDS): step.order = "asc"
                 if any(kw in q for kw in _DESC_KEYWORDS): step.order = "desc"
            
        # ── Default metric resolution ──
        if not step.metric and step.intent_type != "row_level":
            for m in ["revenue", "sales", "profit", "quantity", "gross_sales"]:
                if m in schema.get("metrics", []):
                    step.metric = m
                    break
                    
        # ── Default dimension ──
        if not step.dimensions and schema.get("dimensions") and step.intent_type != "row_level":
            step.dimensions = [schema.get("dimensions")[0]]
            
        # ── Limit enforcement ──
        explicit_limit = _extract_limit_number(question)
        if explicit_limit:
            step.limit = explicit_limit
        elif step.intent_type == "top_n" and not step.limit:
            step.limit = 1

    return plan
