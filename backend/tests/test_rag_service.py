import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.intent import FinalOutput, MultiStepPlan, StepIntent
from app.services import rag_service
from app.core.config import settings


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE business_knowledge (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR,
            dataset_id VARCHAR,
            term VARCHAR NOT NULL,
            knowledge_type VARCHAR NOT NULL,
            meaning VARCHAR NOT NULL,
            confidence DOUBLE DEFAULT 0.0,
            source VARCHAR DEFAULT 'system',
            usage_count INTEGER DEFAULT 0,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE rag_resolution_logs (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR,
            dataset_id VARCHAR,
            query_text VARCHAR NOT NULL,
            keyword_backend VARCHAR NOT NULL,
            vector_backend VARCHAR NOT NULL,
            keyword_terms VARCHAR,
            vector_terms VARCHAR,
            agreement BOOLEAN DEFAULT FALSE,
            keyword_count INTEGER DEFAULT 0,
            vector_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    import app.core.database as db_module

    monkeypatch.setattr(db_module, "_connection", conn)
    monkeypatch.setattr(db_module, "get_connection", lambda: conn)
    monkeypatch.setattr(rag_service, "get_connection", lambda: conn)

    yield conn
    conn.close()


def _make_plan(metric=None):
    return MultiStepPlan(
        query_type="ranking",
        requires_multi_step=False,
        steps=[
            StepIntent(
                step_id=1,
                intent_type="top_n",
                description="Find top party",
                metric=metric,
                dimensions=["party"],
                filters={},
                order="DESC",
                limit=1,
            )
        ],
        final_output=FinalOutput(type="table", description="Show top party"),
    )


def test_retrieve_business_context_prefers_dataset_specific():
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="profit",
        confidence=0.91,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.85,
        tenant_id="user1",
        dataset_id=None,
    )

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")

    assert matches
    assert matches[0]["meaning"] == "profit"


def test_apply_business_context_sets_metric_when_confident():
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.92,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    plan = _make_plan(metric=None)

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")
    result = rag_service.apply_business_context(
        plan=plan,
        question="best party",
        schema={"metrics": ["revenue", "profit"], "semantic_metrics": [], "dimensions": ["party"]},
        matches=matches,
    )

    assert plan.steps[0].metric == "revenue"
    assert result["resolved_terms"] == {"best": "revenue"}
    assert result["ambiguous_terms"] == {}


def test_apply_business_context_ignores_low_confidence():
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.55,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    plan = _make_plan(metric=None)

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")
    result = rag_service.apply_business_context(
        plan=plan,
        question="best party",
        schema={"metrics": ["revenue", "profit"], "semantic_metrics": [], "dimensions": ["party"]},
        matches=matches,
    )

    assert plan.steps[0].metric is None
    assert result["resolved_terms"] == {}


def test_apply_business_context_marks_close_matches_as_ambiguous():
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.84,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="profit",
        confidence=0.80,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    plan = _make_plan(metric=None)

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")
    result = rag_service.apply_business_context(
        plan=plan,
        question="best party",
        schema={"metrics": ["revenue", "profit"], "semantic_metrics": [], "dimensions": ["party"]},
        matches=matches,
    )

    assert plan.steps[0].metric is None
    assert "best" in result["ambiguous_terms"]
    assert result["ambiguous_terms"]["best"][0]["meaning"] == "revenue"


def test_analyze_business_context_resolves_clear_winner():
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.92,
        tenant_id="user1",
        dataset_id="dataset-1",
    )
    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="profit",
        confidence=0.60,
        tenant_id="user1",
        dataset_id="dataset-1",
    )

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")
    analysis = rag_service.analyze_business_context("best party", matches)

    assert analysis["terms"][0]["status"] == "resolved"


def test_learn_from_clarification_stores_metric_mapping():
    result = rag_service.learn_from_clarification(
        selected_option="Revenue",
        ambiguous_terms=["best"],
        schema={"metrics": ["revenue", "profit"], "semantic_metrics": []},
        tenant_id="user1",
        dataset_id="dataset-1",
    )

    assert result["stored"] is True
    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")
    assert matches
    assert matches[0]["term"] == "best"
    assert matches[0]["meaning"] == "revenue"


def test_shadow_mode_logs_keyword_vs_vector(monkeypatch):
    monkeypatch.setattr(settings, "RAG_BACKEND", "keyword")
    monkeypatch.setattr(settings, "VECTOR_SHADOW_MODE", True)

    rag_service.add_business_knowledge(
        term="best",
        knowledge_type="metric",
        meaning="revenue",
        confidence=0.9,
        tenant_id="user1",
        dataset_id="dataset-1",
    )

    monkeypatch.setattr(
        rag_service,
        "_retrieve_business_context_vector",
        lambda question, tenant_id, dataset_id=None: [
            {
                "term": "best",
                "type": "metric",
                "meaning": "profit",
                "confidence": 0.82,
                "tenant_id": tenant_id,
                "dataset_id": dataset_id,
                "source": "system",
                "usage_count": 0,
            }
        ],
    )

    matches = rag_service.retrieve_business_context("best party", "user1", "dataset-1")

    assert matches[0]["meaning"] == "revenue"
    rows = rag_service.get_connection().execute(
        "SELECT keyword_terms, vector_terms, agreement FROM rag_resolution_logs"
    ).fetchall()
    assert len(rows) == 1
    assert "revenue" in rows[0][0]
    assert "profit" in rows[0][1]
    assert rows[0][2] is False
