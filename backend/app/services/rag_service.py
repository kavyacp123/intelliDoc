from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.database import get_connection
from app.models.intent import MultiStepPlan
from app.services.embedding_service import embedding_service
from app.services.vector_index import vector_index


AUTO_RESOLVE_THRESHOLD = 0.80
AMBIGUITY_GAP_THRESHOLD = 0.10
VECTOR_TOP_CONF_THRESHOLD = 0.75
VECTOR_GAP_THRESHOLD = 0.05

logger = logging.getLogger(__name__)


def retrieve_business_context(
    question: str,
    tenant_id: str,
    dataset_id: Optional[str] = None,
) -> List[Dict[str, object]]:
    """
    Retrieve matching business-knowledge entries for the current query.

    This is a lightweight, local RAG layer backed by DuckDB. We match query text
    against known terms and prefer dataset-specific definitions first, then tenant,
    then global entries.
    """
    if settings.RAG_BACKEND == "vector":
        vector_matches = _retrieve_business_context_vector(question, tenant_id, dataset_id)
        if vector_matches:
            return vector_matches
        logger.info("Vector retrieval unavailable or empty, falling back to keyword matching.")
    keyword_matches = _retrieve_business_context_keyword(question, tenant_id, dataset_id)

    if settings.RAG_BACKEND == "keyword" and settings.VECTOR_SHADOW_MODE:
        vector_matches = _retrieve_business_context_vector(question, tenant_id, dataset_id)
        _log_shadow_comparison(
            question=question,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            keyword_matches=keyword_matches,
            vector_matches=vector_matches,
        )

    return keyword_matches


def apply_business_context(
    plan: MultiStepPlan,
    question: str,
    schema: dict,
    matches: List[Dict[str, object]],
) -> Dict[str, object]:
    """
    Apply retrieved business knowledge to the current plan when the match is strong
    and not ambiguous versus the next-best candidate.
    """
    applied: Dict[str, str] = {}
    rules_used: List[str] = []
    analyzed = analyze_business_context(question, matches)

    for term_result in analyzed["terms"]:
        if term_result["status"] != "resolved":
            continue

        top_match = term_result["top_match"]
        term = str(term_result["term"])
        meaning = str(top_match["meaning"])
        knowledge_type = str(top_match["type"])

        if knowledge_type == "metric":
            changed = _apply_metric_resolution(plan, meaning, schema)
            if changed:
                applied[term] = meaning
                rules_used.append(
                    f"Resolved '{term}' to metric '{meaning}' using business knowledge ({top_match['confidence']:.2f})."
                )

        elif knowledge_type == "rule":
            changed = _apply_rule_resolution(plan, meaning)
            if changed:
                applied[term] = meaning
                rules_used.append(
                    f"Applied rule for '{term}': {meaning} ({top_match['confidence']:.2f})."
                )

    resolution_confidence = max(
        (float(term_result["top_match"]["confidence"]) for term_result in analyzed["terms"] if term_result["status"] == "resolved"),
        default=0.0,
    )
    return {
        "resolved_terms": applied,
        "applied_rules": rules_used,
        "confidence": round(resolution_confidence, 2) if applied else 0.0,
        "ambiguous_terms": {
            term_result["term"]: term_result["matches"]
            for term_result in analyzed["terms"]
            if term_result["status"] == "ambiguous"
        },
        "term_results": analyzed["terms"],
    }


def analyze_business_context(
    question: str,
    matches: List[Dict[str, object]],
) -> Dict[str, object]:
    """
    Group matches by ambiguous term and classify each term as resolved, ambiguous,
    or too weak to use automatically.
    """
    q_lower = question.lower()
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for match in matches:
        term = str(match["term"])
        if term.lower() not in q_lower:
            continue
        grouped.setdefault(term, []).append(match)

    term_results: List[Dict[str, object]] = []
    top_threshold = VECTOR_TOP_CONF_THRESHOLD if settings.RAG_BACKEND == "vector" else AUTO_RESOLVE_THRESHOLD
    gap_threshold = VECTOR_GAP_THRESHOLD if settings.RAG_BACKEND == "vector" else AMBIGUITY_GAP_THRESHOLD

    for term, term_matches in grouped.items():
        ranked = sorted(term_matches, key=lambda item: float(item["confidence"]), reverse=True)
        top_match = ranked[0]
        second_match = ranked[1] if len(ranked) > 1 else None
        top_confidence = float(top_match["confidence"])
        confidence_gap = top_confidence - float(second_match["confidence"]) if second_match else 1.0

        if top_confidence < top_threshold:
            status = "weak"
        elif second_match and confidence_gap < gap_threshold:
            status = "ambiguous"
        else:
            status = "resolved"

        term_results.append(
            {
                "term": term,
                "status": status,
                "top_match": top_match,
                "second_match": second_match,
                "confidence_gap": round(confidence_gap, 2) if second_match else None,
                "matches": ranked[:3],
            }
        )

    return {"terms": term_results}


def add_business_knowledge(
    term: str,
    knowledge_type: str,
    meaning: str,
    confidence: float,
    source: str = "system",
    tenant_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> str:
    """Store a business rule for future retrieval."""
    conn = get_connection()
    record_id = str(uuid.uuid4())
    embedding = _build_embedding_payload(term, meaning)
    conn.execute(
        """
        INSERT INTO business_knowledge (id, tenant_id, dataset_id, term, knowledge_type, meaning, confidence, source, usage_count, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [record_id, tenant_id, dataset_id, term, knowledge_type, meaning, confidence, source, 0, embedding],
    )
    refresh_vector_index()
    return record_id


def learn_from_clarification(
    selected_option: str,
    ambiguous_terms: List[str],
    schema: dict,
    tenant_id: str,
    dataset_id: Optional[str] = None,
) -> Dict[str, object]:
    """
    Persist a user clarification as future business knowledge when we can map it safely.
    """
    if not ambiguous_terms:
        return {"stored": False, "reason": "No ambiguous terms provided."}

    normalized = _normalize_selected_option(selected_option, schema)
    if not normalized:
        return {"stored": False, "reason": "Selected option could not be mapped safely."}

    add_business_knowledge(
        term=ambiguous_terms[0],
        knowledge_type=normalized["knowledge_type"],
        meaning=normalized["meaning"],
        confidence=1.0,
        source="user_feedback",
        tenant_id=tenant_id,
        dataset_id=dataset_id,
    )
    conn = get_connection()
    conn.execute(
        """
        UPDATE business_knowledge
        SET usage_count = usage_count + 1
        WHERE term = ? AND meaning = ? AND knowledge_type = ? AND (dataset_id = ? OR dataset_id IS NULL) AND (tenant_id = ? OR tenant_id IS NULL)
        """,
        [ambiguous_terms[0], normalized["meaning"], normalized["knowledge_type"], dataset_id, tenant_id],
    )
    return {
        "stored": True,
        "term": ambiguous_terms[0],
        "meaning": normalized["meaning"],
        "knowledge_type": normalized["knowledge_type"],
    }


def _apply_metric_resolution(plan: MultiStepPlan, meaning: str, schema: dict) -> bool:
    metrics = set(schema.get("metrics", [])) | set(schema.get("semantic_metrics", []))
    if meaning not in metrics:
        return False

    changed = False
    for step in plan.steps:
        if step.intent_type == "row_level":
            continue
        if not step.metric or step.metric not in metrics:
            step.metric = meaning
            changed = True
    return changed


def _apply_rule_resolution(plan: MultiStepPlan, meaning: str) -> bool:
    if "=" not in meaning and ">" not in meaning and "<" not in meaning:
        return False

    changed = False
    for step in plan.steps:
        if step.intent_type == "row_level":
            continue
        col, op, value = _parse_rule_expression(meaning)
        if not col:
            continue
        step.filters = dict(step.filters)
        step.filters[col] = value if op == "=" else f"{op}{value}"
        changed = True
    return changed


def _parse_rule_expression(expr: str) -> tuple[str | None, str | None, str | None]:
    for op in [">=", "<=", ">", "<", "="]:
        if op in expr:
            left, right = expr.split(op, 1)
            return left.strip(), op, right.strip()
    return None, None, None


def _normalize_selected_option(selected_option: str, schema: dict) -> Optional[Dict[str, str]]:
    metrics = set(schema.get("metrics", [])) | set(schema.get("semantic_metrics", []))
    option = selected_option.strip().lower()
    normalized_words = option.replace("-", " ").split()

    for metric in metrics:
        metric_l = metric.lower().replace("_", " ")
        if option == metric_l or option == metric_l.title().lower():
            return {"knowledge_type": "metric", "meaning": metric}
        if metric_l in option:
            return {"knowledge_type": "metric", "meaning": metric}

    if option.startswith("highest ") or option.startswith("lowest "):
        tail = " ".join(normalized_words[1:])
        for metric in metrics:
            if metric.lower().replace("_", " ") == tail:
                return {"knowledge_type": "metric", "meaning": metric}

    return None


def initialize_vector_store() -> None:
    """Build the in-memory vector index if vector retrieval is enabled and dependencies exist."""
    if settings.RAG_BACKEND != "vector":
        return
    refresh_vector_index()


def refresh_vector_index() -> None:
    if settings.RAG_BACKEND != "vector":
        return
    if not embedding_service.is_available() or not vector_index.is_available():
        logger.warning("Vector RAG requested but embedding/FAISS dependencies are unavailable.")
        return

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, term, knowledge_type, meaning, confidence, tenant_id, dataset_id, embedding, source, usage_count
        FROM business_knowledge
        ORDER BY created_at ASC
        """
    ).fetchall()

    records = []
    vectors = []
    pending_updates = []
    for row in rows:
        raw_embedding = row[7]
        vector = embedding_service.deserialize(raw_embedding) if raw_embedding else None
        if vector is None:
            vector = _compose_embedding_vector(row[1], row[3])
            pending_updates.append((embedding_service.serialize(vector), row[0]))

        records.append(
            {
                "id": row[0],
                "term": row[1],
                "type": row[2],
                "meaning": row[3],
                "confidence": float(row[4] or 0.0),
                "tenant_id": row[5],
                "dataset_id": row[6],
                "source": row[8],
                "usage_count": int(row[9] or 0),
            }
        )
        vectors.append(vector)

    if pending_updates:
        conn.executemany("UPDATE business_knowledge SET embedding = ? WHERE id = ?", pending_updates)

    vector_index.build(vectors, records)
    vector_index.save()


def _retrieve_business_context_keyword(
    question: str,
    tenant_id: str,
    dataset_id: Optional[str] = None,
) -> List[Dict[str, object]]:
    conn = get_connection()
    q_lower = question.lower()
    rows = conn.execute(
        """
        SELECT term, knowledge_type, meaning, confidence, tenant_id, dataset_id, source, usage_count
        FROM business_knowledge
        WHERE (? LIKE '%' || lower(term) || '%')
          AND (dataset_id = ? OR dataset_id IS NULL)
          AND (tenant_id = ? OR tenant_id IS NULL)
        ORDER BY
            CASE WHEN dataset_id = ? THEN 0 WHEN dataset_id IS NULL THEN 1 ELSE 2 END,
            CASE WHEN tenant_id = ? THEN 0 WHEN tenant_id IS NULL THEN 1 ELSE 2 END,
            confidence DESC,
            length(term) DESC
        """,
        [q_lower, dataset_id, tenant_id, dataset_id, tenant_id],
    ).fetchall()

    return [
        {
            "term": row[0],
            "type": row[1],
            "meaning": row[2],
            "confidence": float(row[3] or 0.0),
            "tenant_id": row[4],
            "dataset_id": row[5],
            "source": row[6],
            "usage_count": int(row[7] or 0),
        }
        for row in rows
    ]


def _retrieve_business_context_vector(
    question: str,
    tenant_id: str,
    dataset_id: Optional[str] = None,
) -> List[Dict[str, object]]:
    if not embedding_service.is_available() or not vector_index.is_available():
        return []
    if vector_index.index is None:
        refresh_vector_index()
    if vector_index.index is None:
        return []

    query_vector = embedding_service.embed([question])[0]
    raw_matches = vector_index.search(query_vector, k=8)
    filtered = []
    for match in raw_matches:
        if match.get("dataset_id") not in {dataset_id, None}:
            continue
        if match.get("tenant_id") not in {tenant_id, None}:
            continue
        filtered.append(match)
    return filtered


def _build_embedding_payload(term: str, meaning: str) -> Optional[bytes]:
    if not embedding_service.is_available():
        return None
    vector = _compose_embedding_vector(term, meaning)
    return embedding_service.serialize(vector)


def _compose_embedding_vector(term: str, meaning: str) -> List[float]:
    text = f"{term}: {meaning}"
    return embedding_service.embed([text])[0]


def _log_shadow_comparison(
    question: str,
    tenant_id: str,
    dataset_id: Optional[str],
    keyword_matches: List[Dict[str, object]],
    vector_matches: List[Dict[str, object]],
) -> None:
    try:
        conn = get_connection()
        keyword_terms = _summarize_matches(keyword_matches)
        vector_terms = _summarize_matches(vector_matches)
        agreement = keyword_terms[:1] == vector_terms[:1] and bool(keyword_terms or vector_terms)
        log_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO rag_resolution_logs (
                id, tenant_id, dataset_id, query_text, keyword_backend, vector_backend,
                keyword_terms, vector_terms, agreement, keyword_count, vector_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                log_id,
                tenant_id,
                dataset_id,
                question,
                "keyword",
                "vector",
                json.dumps(keyword_terms),
                json.dumps(vector_terms),
                agreement,
                len(keyword_matches),
                len(vector_matches),
            ],
        )
    except Exception as e:
        logger.warning("Failed to log RAG shadow comparison: %s", e)


def _summarize_matches(matches: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        {
            "term": match.get("term"),
            "meaning": match.get("meaning"),
            "confidence": round(float(match.get("confidence", 0.0)), 4),
        }
        for match in matches[:3]
    ]
