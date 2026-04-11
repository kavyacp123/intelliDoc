import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.llm_service import _fallback_refine_query


def test_fallback_refiner_prefixes_clarification():
    refined = _fallback_refine_query("profit of xyz product", "total for last month")
    assert refined == "total for last month profit of xyz product"


def test_fallback_refiner_handles_yes_as_over_time():
    refined = _fallback_refine_query("show revenue", "Yes")
    assert refined == "show revenue over time"


def test_fallback_refiner_handles_structured_answers():
    refined = _fallback_refine_query("show performance", {"metric": "Revenue", "time": "Last month"})
    assert refined == "Revenue Last month show performance"
