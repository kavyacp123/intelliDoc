from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional

from app.models.intent import MultiStepPlan

try:
    from rapidfuzz import process as rapidfuzz_process
except Exception:  # pragma: no cover - optional dependency
    rapidfuzz_process = None


GENERIC_STRUCTURE_TERMS = {
    "performance",
    "show performance",
    "show summary",
    "summary",
    "overview",
    "show data",
}

STOPWORDS = {
    "show", "me", "the", "of", "for", "by", "in", "and", "or", "with",
    "details", "detail", "what", "which", "is", "are", "to", "on", "last",
    "this", "that", "party", "product", "customer", "region", "sales", "profit",
    "revenue", "items", "performance", "top", "best", "highest", "lowest",
}


def build_interaction_response(
    question: str,
    original_plan: MultiStepPlan,
    resolved_plan: MultiStepPlan,
    schema: dict,
    confidence_result: Dict[str, object],
    sample_values: Dict[str, List[str]] | None = None,
) -> Dict[str, object]:
    sample_values = sample_values or {}
    missing_slots = confidence_result.get("missing_slots", [])
    failure_type = classify_failure_type(
        question=question,
        original_plan=original_plan,
        resolved_plan=resolved_plan,
        confidence_result=confidence_result,
        sample_values=sample_values,
    )

    if failure_type == "unknown_entity":
        entity_hint = suggest_entity(question, sample_values)
        if entity_hint:
            return {
                "interaction_type": "entity_suggestion",
                "failure_type": failure_type,
                "question": f'I couldn\'t find "{entity_hint["query"]}". Did you mean one of these?',
                "options": [opt["label"] for opt in entity_hint["options"]],
                "payload": {
                    "type": "entity_suggestion",
                    "message": f'I couldn\'t find "{entity_hint["query"]}". Did you mean:',
                    "options": entity_hint["options"],
                },
            }

    if failure_type == "missing_structure":
        options = _structure_options(schema)
        slot_payload = missing_slots or [
            {
                "key": "metric",
                "question": "Which metric should I use?",
                "options": options,
            }
        ]
        expected_fields = [slot["key"] for slot in slot_payload if slot.get("key")]
        return {
            "interaction_type": "multi_slot_clarification",
            "failure_type": failure_type,
            "question": "I made a best-effort answer, but I need a couple of details to tighten it up.",
            "options": options,
            "payload": {
                "type": "multi_slot_clarification",
                "message": "I made a best guess. Help me tighten it with these details:",
                "questions": slot_payload,
                "expected_fields": expected_fields,
            },
        }

    if failure_type == "partial_intent":
        options = _partial_intent_options(schema)
        slot_payload = missing_slots or [
            {
                "key": "metric",
                "question": "Which metric or view should I use?",
                "options": options,
            }
        ]
        return {
            "interaction_type": "multi_slot_clarification",
            "failure_type": failure_type,
            "question": "I answered with a best guess, but one detail is still fuzzy.",
            "options": options,
            "payload": {
                "type": "multi_slot_clarification",
                "message": "Got it — help me confirm these assumptions:",
                "questions": slot_payload,
                "expected_fields": [slot["key"] for slot in slot_payload if slot.get("key")],
            },
        }

    return {
        "interaction_type": "clarification_options",
        "failure_type": "ambiguity",
        "question": confidence_result.get("clarification_question"),
        "options": confidence_result.get("clarification_options", []),
        "payload": {
            "type": "clarification_options",
            "message": confidence_result.get("clarification_question"),
            "options": [
                {"label": option, "confidence": None}
                for option in confidence_result.get("clarification_options", [])
            ],
        },
    }


def resolve_from_history(
    question: str,
    plan: MultiStepPlan,
    schema: dict,
    session_context: Dict[str, object] | None = None,
) -> Dict[str, object]:
    """Fill missing intent fields from previously established session context."""
    session_context = session_context or {}
    resolved_terms = session_context.get("resolved_terms", {}) or {}
    metrics = set(schema.get("metrics", [])) | set(schema.get("semantic_metrics", []))
    q = question.lower()
    applied: Dict[str, str] = {}

    for term, resolution in resolved_terms.items():
        if term.lower() in q and resolution in metrics:
            for step in plan.steps:
                if step.intent_type == "row_level":
                    continue
                if not step.metric:
                    step.metric = resolution
                    applied[term] = resolution

    last_metric = session_context.get("last_metric")
    generic_follow_up = q.strip() in GENERIC_STRUCTURE_TERMS or q.startswith("show ") and " by " not in q and " of " not in q
    if last_metric in metrics and generic_follow_up:
        for step in plan.steps:
            if step.intent_type != "row_level" and not step.metric:
                step.metric = str(last_metric)
                applied["last_metric"] = str(last_metric)

    last_dimensions = [dim for dim in (session_context.get("last_dimensions") or []) if dim in schema.get("dimensions", [])]
    if generic_follow_up and last_dimensions:
        for step in plan.steps:
            if not step.dimensions:
                step.dimensions = [last_dimensions[0]]

    return {"resolved_terms": applied}


def classify_failure_type(
    question: str,
    original_plan: MultiStepPlan,
    resolved_plan: MultiStepPlan,
    confidence_result: Dict[str, object],
    sample_values: Dict[str, List[str]] | None = None,
) -> str:
    q = question.lower().strip()
    sample_values = sample_values or {}
    issues = {issue["type"] for issue in confidence_result.get("issues", [])}

    if suggest_entity(question, sample_values):
        return "unknown_entity"

    if q in GENERIC_STRUCTURE_TERMS or ("missing_metric" in issues and not any(step.metric for step in original_plan.steps)):
        return "missing_structure"

    if ("weak_mapping" in issues or "missing_metric" in issues) and _has_some_intent(original_plan, resolved_plan):
        return "partial_intent"

    return "ambiguity"


def suggest_entity(question: str, sample_values: Dict[str, List[str]]) -> Optional[Dict[str, object]]:
    entity_text = _extract_entity_candidate(question)
    if not entity_text:
        return None

    all_values = []
    for values in sample_values.values():
        all_values.extend(values)

    if not all_values:
        return None

    matches = _fuzzy_matches(entity_text, all_values)
    if not matches:
        return None

    return {"query": entity_text, "options": matches}


def _extract_entity_candidate(question: str) -> Optional[str]:
    lowered = question.lower()
    patterns = [
        r"\b(?:of|for)\s+([a-z0-9 _-]+?)(?:\s+(?:by|in|last|this|with|and)\b|$)",
        r"\bproduct\s+([a-z0-9 _-]+?)(?:\s+(?:by|in|last|this|with|and)\b|$)",
        r"\bcustomer\s+([a-z0-9 _-]+?)(?:\s+(?:by|in|last|this|with|and)\b|$)",
        r"\bparty\s+([a-z0-9 _-]+?)(?:\s+(?:by|in|last|this|with|and)\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip(" '\"")
            if candidate and candidate not in STOPWORDS:
                return candidate
    return None


def _has_some_intent(original_plan: MultiStepPlan, resolved_plan: MultiStepPlan) -> bool:
    for step in original_plan.steps + resolved_plan.steps:
        if step.metric or step.dimensions or step.filters:
            return True
    return False


def _structure_options(schema: dict) -> List[str]:
    options = []
    for metric in ["revenue", "profit", "sales", "items", "quantity", "amount"]:
        if metric in schema.get("metrics", []) or metric in schema.get("semantic_metrics", []):
            options.append(metric.replace("_", " ").title())
    return options[:3] or ["Revenue", "Profit", "Items"]


def _partial_intent_options(schema: dict) -> List[str]:
    options = _structure_options(schema)
    if schema.get("time_dimensions"):
        options.append("Last month")
    return list(dict.fromkeys(options))[:3]


def _fuzzy_matches(query_value: str, candidates: List[str], threshold: int = 70) -> List[Dict[str, object]]:
    if not candidates:
        return []

    if rapidfuzz_process is not None:
        matches = rapidfuzz_process.extract(query_value, candidates, limit=5)
        return [
            {"label": match[0], "score": float(match[1])}
            for match in matches
            if float(match[1]) >= threshold
        ]

    lowered_candidates = {candidate.lower(): candidate for candidate in candidates}
    close = difflib.get_close_matches(query_value.lower(), list(lowered_candidates.keys()), n=5, cutoff=threshold / 100)
    return [{"label": lowered_candidates[item], "score": 100.0} for item in close]
