import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.intent import FinalOutput, MultiStepPlan, StepIntent
from app.services.interaction_controller import (
    build_interaction_response,
    classify_failure_type,
    suggest_entity,
)


def _make_plan(metric=None, dimensions=None):
    return MultiStepPlan(
        query_type="simple",
        requires_multi_step=False,
        steps=[
            StepIntent(
                step_id=1,
                intent_type="aggregate",
                description="Analyze query",
                metric=metric,
                dimensions=dimensions or [],
                filters={},
            )
        ],
        final_output=FinalOutput(type="table", description="Show result"),
    )


def test_unknown_entity_suggests_similar_sample_values():
    suggestion = suggest_entity(
        "profit of zyx product",
        {"product_name": ["XYZ Product A", "XYZ Product B", "Delta Widget"]},
    )

    assert suggestion is not None
    option_labels = [opt["label"] for opt in suggestion["options"]]
    assert "XYZ Product A" in option_labels


def test_classify_missing_structure_for_generic_query():
    failure = classify_failure_type(
        question="show performance",
        original_plan=_make_plan(metric=None),
        resolved_plan=_make_plan(metric=None),
        confidence_result={"issues": [{"type": "missing_metric", "description": "metric missing"}]},
        sample_values={},
    )

    assert failure == "missing_structure"


def test_build_interaction_response_for_partial_intent():
    response = build_interaction_response(
        question="profit of region",
        original_plan=_make_plan(metric="profit"),
        resolved_plan=_make_plan(metric="profit"),
        schema={"metrics": ["revenue", "profit"], "semantic_metrics": [], "time_dimensions": ["date"]},
        confidence_result={
            "issues": [{"type": "weak_mapping", "description": "weak mapping"}],
            "clarification_question": "Which metric should I use?",
            "clarification_options": ["Revenue", "Profit"],
        },
        sample_values={},
    )

    assert response["failure_type"] == "partial_intent"
    assert response["options"]
