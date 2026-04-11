import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag_metrics_service import compute_rag_metrics


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    conn = duckdb.connect(":memory:")
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
    import app.services.rag_metrics_service as metrics_module

    monkeypatch.setattr(db_module, "_connection", conn)
    monkeypatch.setattr(db_module, "get_connection", lambda: conn)
    monkeypatch.setattr(metrics_module, "get_connection", lambda: conn)

    yield conn
    conn.close()


def test_compute_rag_metrics_summarizes_agreement_and_disagreements():
    import json
    from app.core.database import get_connection

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO rag_resolution_logs
        (id, tenant_id, dataset_id, query_text, keyword_backend, vector_backend, keyword_terms, vector_terms, agreement, keyword_count, vector_count)
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "1", "user1", "ds1", "best party", "keyword", "vector",
            json.dumps([{"term": "best", "meaning": "revenue", "confidence": 0.9}]),
            json.dumps([{"term": "best", "meaning": "revenue", "confidence": 0.88}, {"term": "best", "meaning": "profit", "confidence": 0.83}]),
            True, 1, 2,
            "2", "user1", "ds1", "top performance", "keyword", "vector",
            json.dumps([{"term": "top", "meaning": "revenue", "confidence": 0.86}]),
            json.dumps([{"term": "top", "meaning": "profit", "confidence": 0.81}, {"term": "top", "meaning": "revenue", "confidence": 0.79}]),
            False, 1, 2,
        ],
    )

    result = compute_rag_metrics("user1", "ds1")

    assert result["total_queries"] == 2
    assert result["agreement_rate"] == 0.5
    assert result["vector_ambiguity_rate"] == 1.0
    assert result["keyword_ambiguity_rate"] == 0.0
    assert result["avg_vector_top_conf"] == 0.845
    assert result["avg_vector_gap"] == 0.035
    assert result["top_disagreements"][0]["term"] == "top"
