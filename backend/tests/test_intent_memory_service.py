import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.intent import FinalOutput, MultiStepPlan, StepIntent
from app.services.intent_memory_service import apply_correction_to_plan, build_plan_from_memory
from app.services.intent_processor import enhance_intent


def _plan():
    return MultiStepPlan(
        query_type="simple",
        requires_multi_step=False,
        steps=[
            StepIntent(
                step_id=1,
                intent_type="top_n",
                description="Top customers",
                metric="gross_total",
                dimensions=["party_name"],
                filters={},
                order="DESC",
                limit=10,
            )
        ],
        final_output=FinalOutput(type="table", description="Show top customers"),
    )


def test_build_plan_from_memory_round_trip():
    original = _plan()
    restored = build_plan_from_memory({"last_intent": original.model_dump()})

    assert restored is not None
    assert restored.steps[0].metric == "gross_total"


def test_apply_correction_changes_metric_and_limit():
    plan = _plan()
    result = apply_correction_to_plan(
        plan,
        "use profit and show top 20",
        {
            "metrics": ["gross_total", "net_profit"],
            "semantic_metrics": [],
            "dimensions": ["party_name"],
            "time_dimensions": ["invoice_date"],
        },
    )

    assert result["changed"] is True
    assert plan.steps[0].metric == "net_profit"
    assert plan.steps[0].limit == 20


def test_apply_correction_adds_time_filter():
    plan = _plan()
    result = apply_correction_to_plan(
        plan,
        "only last month",
        {
            "metrics": ["gross_total"],
            "semantic_metrics": [],
            "dimensions": ["party_name"],
            "time_dimensions": ["invoice_date"],
        },
    )

    assert result["changed"] is True
    assert plan.steps[0].filters["invoice_date"] == "__last_month"


def test_step_intent_accepts_metric_list_from_llm():
    step = StepIntent(
        step_id=1,
        intent_type="aggregate",
        description="bad LLM shape",
        metric=["gross_total", "line_quantity"],
        dimensions="product",
    )

    assert step.metric == "gross_total"
    assert step.dimensions == ["product"]


def test_enhance_intent_normalizes_sr_date_and_ignores_dataset_name_filter():
    plan = _plan()
    plan.steps[0].metric = "revenue"
    plan.steps[0].dimensions = ["_month"]
    plan.steps[0].filters = {"_month": "SR 22-23"}

    enhanced = enhance_intent(
        plan,
        "Show month-wise sales trend by gross total from April 2022 to March 2023",
        {
            "metrics": ["gross_total", "revenue"],
            "semantic_metrics": [],
            "dimensions": ["customer"],
            "time_dimensions": ["date"],
        },
    )

    step = enhanced.steps[0]
    assert step.metric == "gross_total"
    assert "_month" not in step.filters
    assert step.filters["date"] == {"gte": "2022-04-01", "lte": "2023-03-31"}
