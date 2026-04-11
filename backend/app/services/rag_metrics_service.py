from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from app.core.database import get_connection


def compute_rag_metrics(tenant_id: str, dataset_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()

    if dataset_id:
        rows = conn.execute(
            """
            SELECT query_text, keyword_terms, vector_terms, agreement, keyword_count, vector_count
            FROM rag_resolution_logs
            WHERE tenant_id = ? AND dataset_id = ?
            ORDER BY created_at DESC
            """,
            [tenant_id, dataset_id],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT query_text, keyword_terms, vector_terms, agreement, keyword_count, vector_count
            FROM rag_resolution_logs
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            """,
            [tenant_id],
        ).fetchall()

    total = len(rows)
    if total == 0:
        return {
            "total_queries": 0,
            "agreement_rate": 0.0,
            "vector_ambiguity_rate": 0.0,
            "keyword_ambiguity_rate": 0.0,
            "avg_vector_top_conf": 0.0,
            "avg_vector_gap": 0.0,
            "top_disagreements": [],
        }

    agreements = 0
    vector_ambiguous = 0
    keyword_ambiguous = 0
    vector_top_conf_total = 0.0
    vector_gap_total = 0.0
    vector_gap_count = 0
    disagreement_counter: Counter[tuple[str, str, str]] = Counter()

    for query_text, keyword_raw, vector_raw, agreement, keyword_count, vector_count in rows:
        keyword_terms = _parse_terms(keyword_raw)
        vector_terms = _parse_terms(vector_raw)

        if agreement:
            agreements += 1

        if (vector_count or 0) > 1:
            vector_ambiguous += 1
        if (keyword_count or 0) > 1:
            keyword_ambiguous += 1

        if vector_terms:
            vector_top_conf_total += float(vector_terms[0].get("confidence", 0.0))
        if len(vector_terms) > 1:
            vector_gap_total += float(vector_terms[0].get("confidence", 0.0)) - float(vector_terms[1].get("confidence", 0.0))
            vector_gap_count += 1

        if not agreement:
            term = str((vector_terms[0].get("term") if vector_terms else keyword_terms[0].get("term") if keyword_terms else "") or "")
            keyword_label = _term_label(keyword_terms)
            vector_label = _term_label(vector_terms)
            disagreement_counter[(term, keyword_label, vector_label)] += 1

    top_disagreements = [
        {
            "term": term,
            "keyword": keyword.split(" | ") if keyword else [],
            "vector": vector.split(" | ") if vector else [],
            "count": count,
        }
        for (term, keyword, vector), count in disagreement_counter.most_common(10)
    ]

    return {
        "total_queries": total,
        "agreement_rate": round(agreements / total, 4),
        "vector_ambiguity_rate": round(vector_ambiguous / total, 4),
        "keyword_ambiguity_rate": round(keyword_ambiguous / total, 4),
        "avg_vector_top_conf": round(vector_top_conf_total / total, 4),
        "avg_vector_gap": round((vector_gap_total / vector_gap_count), 4) if vector_gap_count else 0.0,
        "top_disagreements": top_disagreements,
    }


def _parse_terms(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _term_label(terms: List[Dict[str, Any]]) -> str:
    return " | ".join(str(term.get("meaning", "")) for term in terms[:3] if term.get("meaning"))
