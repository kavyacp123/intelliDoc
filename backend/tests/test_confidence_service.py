import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.intent import FinalOutput, MultiStepPlan, StepIntent
from app.services.confidence_service import score_plan_confidence


def _make_plan(metric: str | None, dimension: str | None = "party") -> MultiStepPlan:
    return MultiStepPlan(
        query_type="ranking",
        requires_multi_step=False,
        steps=[
            StepIntent(
                step_id=1,
                intent_type="top_n",
                description="Rank parties",
                metric=metric,
                dimensions=[dimension] if dimension else [],
                filters={},
                order="DESC",
                limit=1,
            )
        ],
        final_output=FinalOutput(type="table", description="Show the result"),
    )


def test_low_confidence_for_ambiguous_best_without_semantics():
    schema = {
        "metrics": ["revenue", "items"],
        "dimensions": ["party"],
        "time_dimensions": [],
    }
    original = _make_plan(metric=None)
    resolved = _make_plan(metric="revenue")

    result = score_plan_confidence(
        question="best party",
        original_plan=original,
        resolved_plan=resolved,
        schema=schema,
        semantics={},
    )

    assert result["needs_clarification"] is True
    assert result["confidence"] < 0.7
    assert result["clarification_question"]
    assert result["clarification_options"]


def test_high_confidence_when_semantics_resolve_term():
    schema = {
        "metrics": ["revenue", "profit"],
        "dimensions": ["party"],
        "time_dimensions": [],
    }
    original = _make_plan(metric="profit")
    resolved = _make_plan(metric="profit")

    result = score_plan_confidence(
        question="show profit by party",
        original_plan=original,
        resolved_plan=resolved,
        schema=schema,
        semantics={"profit": "revenue - expense"},
    )

    assert result["needs_clarification"] is False
    assert result["confidence"] >= 0.8


def test_risky_query_requests_definition():
    schema = {
        "metrics": ["revenue", "profit"],
        "dimensions": ["party"],
        "time_dimensions": [],
    }
    original = _make_plan(metric="revenue")
    resolved = _make_plan(metric="revenue")

    result = score_plan_confidence(
        question="which party is risky",
        original_plan=original,
        resolved_plan=resolved,
        schema=schema,
        semantics={},
    )

    assert result["needs_clarification"] is True
    assert result["clarification_question"] == "What should count as risky here?"


def test_close_rag_matches_trigger_specific_clarification():
    schema = {
        "metrics": ["revenue", "profit", "items"],
        "dimensions": ["party"],
        "time_dimensions": [],
    }
    original = _make_plan(metric=None)
    resolved = _make_plan(metric=None)

    result = score_plan_confidence(
        question="best party",
        original_plan=original,
        resolved_plan=resolved,
        schema=schema,
        semantics={},
        rag_resolved_terms={},
        rag_term_results=[
            {
                "term": "best",
                "status": "ambiguous",
                "top_match": {"meaning": "revenue", "confidence": 0.84},
                "second_match": {"meaning": "profit", "confidence": 0.80},
                "matches": [
                    {"meaning": "revenue", "confidence": 0.84},
                    {"meaning": "profit", "confidence": 0.80},
                ],
            }
        ],
    )

    assert result["needs_clarification"] is True
    assert result["clarification_question"] == "How should 'best' be defined?"
    assert result["clarification_options"][:2] == ["Revenue", "Profit"]
