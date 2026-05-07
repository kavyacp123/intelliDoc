from __future__ import annotations

from typing import Dict, List, Tuple

from app.models.intent import MultiStepPlan


AMBIGUOUS_TERMS = {
    "best",
    "top",
    "highest",
    "lowest",
    "least",
    "performance",
    "risky",
    "risk",
    "high value",
    "valuable",
}


def score_plan_confidence(
    question: str,
    original_plan: MultiStepPlan,
    resolved_plan: MultiStepPlan,
    schema: dict,
    semantics: Dict[str, str] | None = None,
    rag_resolved_terms: Dict[str, str] | None = None,
    rag_term_results: List[Dict[str, object]] | None = None,
    session_context: Dict[str, object] | None = None,
) -> Dict[str, object]:
    """
    Score whether the current plan is safe to execute or should ask for clarification.

    This is intentionally deterministic. It catches the main trust killers:
    vague business terms, silent metric defaults, and plans that only work because
    we guessed a metric or dimension.
    """
    semantics = semantics or {}
    rag_resolved_terms = rag_resolved_terms or {}
    rag_term_results = rag_term_results or []
    session_context = session_context or {}
    q = question.lower()
    issues: List[Dict[str, str]] = []
    score = 0.95

    metric_names = set(schema.get("metrics", [])) | set(semantics.keys())
    dimension_names = set(schema.get("dimensions", []))

    has_ambiguous_term = any(term in q for term in AMBIGUOUS_TERMS)
    resolved_terms = _find_resolved_terms(q, semantics)
    resolved_terms.update(rag_resolved_terms)
    session_resolved_terms = session_context.get("resolved_terms", {}) or {}
    for term, resolution in session_resolved_terms.items():
        if term.lower() in q:
            resolved_terms[term] = resolution
            score += 0.15

    rag_option_map = {
        str(term_result["term"]): [_humanize_option(str(match["meaning"])) for match in term_result.get("matches", [])]
        for term_result in rag_term_results
        if term_result.get("status") == "ambiguous"
    }

    for term_result in rag_term_results:
        status = term_result.get("status")
        top_match = term_result.get("top_match")
        if not top_match:
            continue

        top_confidence = float(top_match["confidence"])
        if status == "resolved":
            score += min(0.25, top_confidence * 0.2)
        elif status == "ambiguous":
            score -= 0.30
            issues.append(
                {
                    "type": "ambiguity",
                    "description": (
                        f"Business knowledge has multiple close meanings for '{term_result['term']}' "
                        f"({top_match['meaning']} vs {term_result['second_match']['meaning']})."
                    ),
                }
            )
        elif status == "weak":
            score -= 0.12
            issues.append(
                {
                    "type": "weak_mapping",
                    "description": f"Business knowledge match for '{term_result['term']}' is too weak to trust automatically.",
                }
            )

    if has_ambiguous_term and not resolved_terms:
        score -= 0.35
        issues.append(
            {
                "type": "ambiguity",
                "description": "The query uses a vague business term that is not defined in schema or semantic rules.",
            }
        )

    for original_step, resolved_step in zip(original_plan.steps, resolved_plan.steps):
        if resolved_step.intent_type == "row_level":
            continue

        if not original_step.metric and resolved_step.metric:
            score -= 0.18
            issues.append(
                {
                    "type": "weak_mapping",
                    "description": f"Defaulted to metric '{resolved_step.metric}' because the query did not specify one clearly.",
                }
            )
        elif original_step.metric and original_step.metric != resolved_step.metric:
            score -= 0.22
            issues.append(
                {
                    "type": "weak_mapping",
                    "description": f"Mapped requested metric '{original_step.metric}' to '{resolved_step.metric}'.",
                }
            )

        if not original_step.dimensions and resolved_step.dimensions:
            score -= 0.08
            issues.append(
                {
                    "type": "weak_mapping",
                    "description": f"Defaulted to dimension '{resolved_step.dimensions[0]}'.",
                }
            )

        if not resolved_step.metric and resolved_step.intent_type != "row_level":
            score -= 0.25
            issues.append(
                {
                    "type": "missing_metric",
                    "description": "The plan does not contain a clear metric for a non-row-level step.",
                }
            )

    if any(term in q for term in ["risky", "risk", "high value", "performance"]) and not resolved_terms:
        score -= 0.25
        issues.append(
            {
                "type": "unknown_term",
                "description": "The query depends on a business definition that is not currently known to the system.",
            }
        )

    if not metric_names:
        score -= 0.20
        issues.append(
            {
                "type": "missing_metric",
                "description": "No numeric metrics were detected in the active dataset schema.",
            }
        )

    score = max(0.0, min(1.0, score))
    needs_clarification = score < 0.70 and any(
        issue["type"] in {"ambiguity", "unknown_term", "weak_mapping", "missing_metric"}
        for issue in issues
    )

    clarification_question, options = build_clarification(
        question=question,
        issues=issues,
        metrics=sorted(metric_names),
        dimensions=sorted(dimension_names),
        resolved_terms=resolved_terms,
        rag_option_map=rag_option_map,
    )

    if not needs_clarification:
        clarification_question = None
        options = []

    slot_scores = _build_slot_scores(original_plan, resolved_plan, metrics=sorted(metric_names), dimensions=sorted(dimension_names))
    missing_slots = _infer_missing_slots(
        question=question,
        issues=issues,
        metrics=sorted(metric_names),
        dimensions=sorted(dimension_names),
        time_dimensions=sorted(schema.get("time_dimensions", [])),
        rag_option_map=rag_option_map,
    )
    interpretation = _describe_interpretation(resolved_plan)

    return {
        "confidence": round(score, 2),
        "issues": issues,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "clarification_options": options,
        "clarification_terms": _detect_ambiguous_terms(question),
        "resolved_terms": resolved_terms,
        "slot_scores": slot_scores,
        "missing_slots": missing_slots,
        "execution_strategy": "attempt_with_best_guess" if needs_clarification else "direct_answer",
        "interpretation": interpretation,
    }


def build_clarification(
    question: str,
    issues: List[Dict[str, str]],
    metrics: List[str],
    dimensions: List[str],
    resolved_terms: Dict[str, str],
    rag_option_map: Dict[str, List[str]] | None = None,
) -> Tuple[str | None, List[str]]:
    q = question.lower()
    issue_types = {issue["type"] for issue in issues}
    rag_option_map = rag_option_map or {}

    for term, options in rag_option_map.items():
        if term in q and options:
            return f"How should '{term}' be defined?", _dedupe(options)[:3]

    if "ambiguity" in issue_types and any(term in q for term in ["best", "top", "highest", "lowest", "least"]):
        options = _metric_options(metrics)
        if options:
            return "How should this ranking be defined?", options

    if any(term in q for term in ["risky", "risk"]):
        options = _risk_options(metrics)
        return "What should count as risky here?", options

    if "high value" in q or "valuable" in q:
        options = _value_options(metrics)
        return "How should high value be defined?", options

    if "missing_metric" in issue_types or "weak_mapping" in issue_types:
        options = _metric_options(metrics)
        if options:
            return "Which metric should I use for this query?", options

    if not resolved_terms and dimensions:
        return "Which field should I break this down by?", dimensions[:3]

    return None, []


def _find_resolved_terms(question: str, semantics: Dict[str, str]) -> Dict[str, str]:
    resolved = {}
    q = question.lower()
    for name, expr in semantics.items():
        if name.lower() in q:
            resolved[name] = expr
    return resolved


def _detect_ambiguous_terms(question: str) -> List[str]:
    q = question.lower()
    return [term for term in sorted(AMBIGUOUS_TERMS, key=len, reverse=True) if term in q]


def _metric_options(metrics: List[str]) -> List[str]:
    preferred = []
    for metric in ["revenue", "sales", "profit", "quantity", "items", "amount", "value"]:
        if metric in metrics:
            preferred.append(_humanize_metric(metric))
    for metric in metrics:
        label = _humanize_metric(metric)
        if label not in preferred:
            preferred.append(label)
    return preferred[:3]


def _risk_options(metrics: List[str]) -> List[str]:
    options = []
    if "revenue" in metrics or "sales" in metrics:
        options.append("Lowest revenue")
    if "profit" in metrics:
        options.append("Lowest profit")
    if "quantity" in metrics or "items" in metrics:
        options.append("Lowest sales volume")
    if not options:
        options = ["Lowest value metric", "Most negative trend", "Needs a custom rule"]
    return options[:3]


def _value_options(metrics: List[str]) -> List[str]:
    options = []
    if "revenue" in metrics or "sales" in metrics:
        options.append("Revenue above a threshold")
    if "profit" in metrics:
        options.append("Profit above a threshold")
    if "quantity" in metrics or "items" in metrics:
        options.append("High purchase volume")
    if not options:
        options = ["Use a numeric threshold", "Use a ranking metric", "Needs a business rule"]
    return options[:3]


def _humanize_metric(metric: str) -> str:
    return metric.replace("_", " ").title()


def _humanize_option(value: str) -> str:
    return value.replace("_", " ").title()


def _dedupe(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _build_slot_scores(
    original_plan: MultiStepPlan,
    resolved_plan: MultiStepPlan,
    metrics: List[str],
    dimensions: List[str],
) -> Dict[str, float]:
    original_step = original_plan.steps[0] if original_plan.steps else None
    resolved_step = resolved_plan.steps[0] if resolved_plan.steps else None
    metric_score = 0.95 if original_step and original_step.metric else 0.62 if resolved_step and resolved_step.metric else 0.25
    dimension_score = 0.95 if original_step and original_step.dimensions else 0.70 if resolved_step and resolved_step.dimensions else 0.40
    timeframe_score = 0.90 if any(dim in {"month", "year", "quarter", "week", "day"} for dim in dimensions) else 0.55
    return {
        "metric": round(metric_score, 2),
        "dimension": round(dimension_score, 2),
        "timeframe": round(timeframe_score, 2),
    }


def _infer_missing_slots(
    question: str,
    issues: List[Dict[str, str]],
    metrics: List[str],
    dimensions: List[str],
    time_dimensions: List[str],
    rag_option_map: Dict[str, List[str]],
) -> List[Dict[str, object]]:
    slots: List[Dict[str, object]] = []
    issue_types = {issue["type"] for issue in issues}
    q = question.lower()

    for term, options in rag_option_map.items():
        if term in q and options:
            slots.append({"key": term, "question": f"How should '{term}' be defined?", "options": options[:3]})

    if "missing_metric" in issue_types or "weak_mapping" in issue_types or any(term in q for term in ["best", "top", "highest", "lowest", "least"]):
        metric_options = _metric_options(metrics)
        if metric_options:
            slots.append({"key": "metric", "question": "Which metric should I use?", "options": metric_options})

    if time_dimensions and any(token in q for token in ["trend", "over time", "month", "year", "daily", "weekly"]) is False and "missing_structure" in issue_types:
        slots.append({
            "key": "timeframe",
            "question": "What time period should I use?",
            "options": ["Last 30 days", "Last quarter", "This year", "All time"],
        })

    if not slots and dimensions and "missing_structure" in issue_types:
        slots.append({
            "key": "dimension",
            "question": "Which field should I break this down by?",
            "options": [_humanize_metric(dim) for dim in dimensions[:3]],
        })

    deduped: List[Dict[str, object]] = []
    seen = set()
    for slot in slots:
        key = slot.get("key")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(slot)
    return deduped


def _describe_interpretation(plan: MultiStepPlan) -> str:
    if not plan.steps:
        return "I could not form a reliable interpretation of the question."
    parts = []
    for step in plan.steps:
        metric = step.metric or "count"
        dims = ", ".join(step.dimensions) if step.dimensions else "overall"
        parts.append(f"{step.intent_type} using {metric} by {dims}")
    return "I interpreted your request as: " + " then ".join(parts) + "."
