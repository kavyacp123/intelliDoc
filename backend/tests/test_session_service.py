import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.session_service import SessionService


def test_pending_interaction_round_trip():
    service = SessionService()
    session_id = service.create_or_update_pending_interaction(
        session_id=None,
        tenant_id="user1",
        dataset_id="ds1",
        interaction={
            "original_query": "show performance",
            "questions": [{"key": "metric"}, {"key": "time"}],
        },
    )

    pending = service.get_pending_interaction(session_id, "user1")
    assert pending is not None
    assert pending["original_query"] == "show performance"
    assert service.is_complete(session_id, "user1") is False

    service.add_answer(session_id, "user1", "metric", "Revenue")
    assert service.is_complete(session_id, "user1") is False

    service.add_answer(session_id, "user1", "time", "Last month")
    assert service.is_complete(session_id, "user1") is True

    service.clear_pending_interaction(session_id, "user1")
    assert service.get_pending_interaction(session_id, "user1") is None


def test_session_context_round_trip():
    service = SessionService()
    session_id = service.merge_session_context(
        None,
        "user1",
        dataset_id="ds1",
        resolved_terms={"best": "revenue"},
        last_metric="revenue",
        last_dimensions=["party"],
    )

    context = service.get_session_context(session_id, "user1")
    assert context["resolved_terms"]["best"] == "revenue"
    assert context["last_metric"] == "revenue"
    assert context["last_dimensions"] == ["party"]
