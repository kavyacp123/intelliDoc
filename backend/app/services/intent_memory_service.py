from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.models.intent import MultiStepPlan


TIME_CORRECTIONS = {
    "last month": "__last_month",
    "this month": "__this_month",
    "last 30 days": "__last_30_days",
    "last quarter": "__last_quarter",
    "this year": "__this_year",
    "all time": None,
}


def build_plan_from_memory(
    session_context: Dict[str, Any],
) -> Optional[MultiStepPlan]:
    raw_intent = session_context.get("last_intent")
    if not raw_intent:
        return None
    try:
        return MultiStepPlan(**raw_intent)
    except Exception:
        return None


def apply_correction_to_plan(
    plan: MultiStepPlan,
    correction_text: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministically edit the previous plan for natural follow-ups like:
    "use profit", "last month", "break it down by region", "top 20".
    """
    text = correction_text.lower().strip()
    if not text:
        return {"changed": False, "changes": []}

    changes: List[str] = []
    metric = _find_metric(text, schema)
    dimension = _find_dimension(text, schema)
    limit = _find_limit(text)
    time_filter = _find_time_filter(text)
    date_col = _first_time_column(schema)

    for step in plan.steps:
        if step.intent_type == "row_level":
            continue

        if metric and step.metric != metric:
            step.metric = metric
            changes.append(f"metric={metric}")

        if dimension:
            if dimension not in step.dimensions:
                step.dimensions = [dimension]
                changes.append(f"dimension={dimension}")

        if limit:
            step.limit = limit
            if step.intent_type == "aggregate":
                step.intent_type = "top_n"
            changes.append(f"limit={limit}")

        if time_filter is not _NO_TIME_MATCH and date_col:
            step.filters = dict(step.filters or {})
            if time_filter is None:
                if date_col in step.filters:
                    step.filters.pop(date_col, None)
                    changes.append("timeframe=all_time")
            else:
                step.filters[date_col] = time_filter
                changes.append(f"timeframe={_humanize_time_filter(time_filter)}")

    if "lowest" in text or "least" in text or "bottom" in text:
        for step in plan.steps:
            if step.intent_type != "row_level":
                step.order = "ASC"
        changes.append("order=ASC")
    elif "highest" in text or "top" in text or "best" in text:
        for step in plan.steps:
            if step.intent_type != "row_level":
                step.order = "DESC"
        changes.append("order=DESC")

    return {"changed": bool(changes), "changes": list(dict.fromkeys(changes))}


def describe_plan_edit(changes: List[str]) -> str:
    if not changes:
        return "Updated the previous answer with your correction."
    readable = [change.replace("_", " ") for change in changes]
    return "Updated the previous answer: " + ", ".join(readable) + "."


_NO_TIME_MATCH = object()


def _find_metric(text: str, schema: Dict[str, Any]) -> Optional[str]:
    metrics = list(schema.get("metrics", [])) + list(schema.get("semantic_metrics", []))
    return _find_named_value(text, metrics, aliases={
        "revenue": ["revenue", "sales", "gross revenue", "gross total"],
        "profit": ["profit", "net profit", "margin"],
        "quantity": ["quantity", "volume", "units", "items"],
    })


def _find_dimension(text: str, schema: Dict[str, Any]) -> Optional[str]:
    dimensions = list(schema.get("dimensions", []))
    return _find_named_value(text, dimensions, aliases={
        "customer": ["customer", "customers", "party", "client"],
        "region": ["region", "state", "zone", "area"],
        "product": ["product", "item", "sku"],
        "month": ["month", "monthly"],
        "year": ["year", "yearly", "annual"],
    })


def _find_named_value(
    text: str,
    candidates: List[str],
    aliases: Dict[str, List[str]],
) -> Optional[str]:
    normalized = {candidate.lower().replace("_", " "): candidate for candidate in candidates}
    for label, original in normalized.items():
        if re.search(rf"\b{re.escape(label)}\b", text):
            return original

    for concept, words in aliases.items():
        if not any(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
            continue
        for label, original in normalized.items():
            if concept in label or any(word in label for word in words):
                return original
    return None


def _find_limit(text: str) -> Optional[int]:
    match = re.search(r"\b(?:top|first|show|limit)\s+(\d{1,3})\b", text)
    if not match:
        return None
    return max(1, min(100, int(match.group(1))))


def _find_time_filter(text: str):
    for phrase, token in TIME_CORRECTIONS.items():
        if phrase in text:
            return token
    return _NO_TIME_MATCH


def _first_time_column(schema: Dict[str, Any]) -> Optional[str]:
    time_columns = schema.get("time_dimensions") or []
    return time_columns[0] if time_columns else None


def _humanize_time_filter(token: str) -> str:
    return token.strip("_").replace("_", " ")
