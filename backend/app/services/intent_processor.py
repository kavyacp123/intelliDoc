from app.models.intent import QueryIntent
import re

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
    # Match patterns like "top 5", "bottom 3", "best 10"
    match = re.search(r'\b(?:top|bottom|best|worst|first|last)\s+(\d+)\b', question.lower())
    if match:
        return int(match.group(1))
    return None


from app.models.intent import MultiStepPlan, StepIntent


def _preferred_metric(question: str, metrics: list[str], semantic_metrics: list[str]) -> str | None:
    q = question.lower()
    all_metrics = metrics + semantic_metrics
    metric_set = set(all_metrics)

    if "gross total" in q and "gross_total" in metric_set:
        return "gross_total"
    if "allocated gross" in q and "allocated_gross_total" in metric_set:
        return "allocated_gross_total"
    if ("net sales" in q or "excluding gst" in q or "excluding tax" in q or "exclude gst" in q) and "allocated_revenue" in metric_set:
        return "allocated_revenue"
    if ("net sales" in q or "excluding gst" in q or "excluding tax" in q or "exclude gst" in q) and "revenue" in metric_set:
        return "revenue"
    if "quantity" in q and "line_quantity" in metric_set:
        return "line_quantity"
    if "quantity" in q:
        for metric in ["quantity", "items", "line_item_count"]:
            if metric in metric_set:
                return metric
    if ("revenue" in q or "sales" in q) and "allocated_revenue" in metric_set:
        return "allocated_revenue"
    if ("revenue" in q or "sales" in q) and "revenue" in metric_set:
        return "revenue"
    return None


def _preferred_dimension(question: str, dimensions: list[str]) -> str | None:
    q = question.lower()
    dim_set = set(dimensions)
    if any(word in q for word in ["customer", "customers", "buyer", "party"]):
        for dim in ["customer", "buyer", "company", "particulars"]:
            if dim in dim_set:
                return dim
    if any(word in q for word in ["product", "item", "items"]):
        for dim in ["product", "product_name"]:
            if dim in dim_set:
                return dim
    return None


def _extract_explicit_date_range(question: str) -> dict | None:
    q = question.lower()
    if "april 2022" in q and "march 2023" in q:
        return {"gte": "2022-04-01", "lte": "2023-03-31"}
    return None


def _clean_filters(filters: dict, schema: dict) -> dict:
    cleaned = {}
    known = set(schema.get("metrics", [])) | set(schema.get("dimensions", [])) | set(schema.get("time_dimensions", []))
    for key, value in (filters or {}).items():
        key_s = str(key).strip()
        value_s = str(value).lower()
        if re.search(r"\bsr\s*[- ]?\s*22\s*[- ]?\s*23\b", value_s):
            continue
        if key_s.lower().strip("_") in {"month", "year", "fy", "financial_year"} and key_s not in known:
            continue
        cleaned[key_s] = value
    return cleaned

def enhance_intent(plan: MultiStepPlan, question: str, schema: dict) -> MultiStepPlan:
    """
    Hybrid Rule Engine: applies deterministic python rules to augment
    or override LLM intent. Applied to each step.
    """
    q = question.lower()
    preferred_metric = _preferred_metric(q, schema.get("metrics", []), schema.get("semantic_metrics", []))
    preferred_dimension = _preferred_dimension(q, schema.get("dimensions", []))
    date_range = _extract_explicit_date_range(q)
    date_col = (schema.get("time_dimensions") or [None])[0]
    
    for step in plan.steps:
        step.filters = _clean_filters(step.filters, schema)

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
        if preferred_metric and step.intent_type != "row_level":
            step.metric = preferred_metric

        if not step.metric and step.intent_type != "row_level":
            for m in ["allocated_revenue", "revenue", "gross_total", "sales", "profit", "quantity", "line_quantity", "gross_sales"]:
                if m in schema.get("metrics", []) or m in schema.get("semantic_metrics", []):
                    step.metric = m
                    break
                    
        # ── Default dimension ──
        if preferred_dimension and step.intent_type != "row_level":
            step.dimensions = [preferred_dimension]

        if not step.dimensions and schema.get("dimensions") and step.intent_type != "row_level":
            step.dimensions = [schema.get("dimensions")[0]]

        if date_range and date_col and step.intent_type != "row_level":
            step.filters = dict(step.filters or {})
            step.filters[date_col] = date_range
            
        # ── Limit enforcement ──
        explicit_limit = _extract_limit_number(question)
        if explicit_limit:
            step.limit = explicit_limit
        elif step.intent_type == "top_n" and not step.limit:
            step.limit = 1

    return plan
