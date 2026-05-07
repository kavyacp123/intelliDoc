from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None

from app.core.config import settings


class SessionService:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
        self._redis = self._build_redis_client()

    def _build_redis_client(self):
        if redis is None:
            return None
        try:
            client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _key(self, session_id: str, tenant_id: str) -> str:
        return f"session:{tenant_id}:{session_id}"

    def _load_record(self, session_id: Optional[str], tenant_id: str) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None

        if self._redis is not None:
            try:
                raw = self._redis.get(self._key(session_id, tenant_id))
                if raw:
                    return json.loads(raw)
            except Exception:
                pass

        record = self._sessions.get(session_id)
        if not record or record.get("tenant_id") != tenant_id:
            return None
        return record

    def _save_record(self, session_id: str, tenant_id: str, record: Dict[str, Any]) -> None:
        if self._redis is not None:
            try:
                self._redis.setex(self._key(session_id, tenant_id), self._ttl_seconds, json.dumps(record))
            except Exception:
                pass
        self._sessions[session_id] = record

    def _default_context(self) -> Dict[str, Any]:
        return {"resolved_terms": {}, "last_metric": None, "last_dimensions": []}

    def create_or_update_pending_interaction(
        self,
        session_id: Optional[str],
        tenant_id: str,
        dataset_id: Optional[str],
        interaction: Dict[str, Any],
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        existing = self._load_record(sid, tenant_id) or {}
        questions = interaction.get("questions", [])
        expected_fields = interaction.get("expected_fields") or [
            question["key"] for question in questions if question.get("key")
        ]
        record = {
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "session_context": existing.get("session_context", self._default_context()),
            "pending_interaction": {
                "original_query": interaction.get("original_query"),
                "failure_type": interaction.get("failure_type"),
                "interaction_type": interaction.get("interaction_type"),
                "questions": questions,
                "answers": interaction.get("answers", {}),
                "expected_fields": expected_fields,
                "context": interaction.get("context", {}),
            },
            "updated_at": time.time(),
        }
        self._save_record(sid, tenant_id, record)
        return sid

    def get_pending_interaction(
        self,
        session_id: Optional[str],
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        session = self._load_record(session_id, tenant_id)
        if not session:
            return None
        return session.get("pending_interaction")

    def clear_pending_interaction(self, session_id: Optional[str], tenant_id: str) -> None:
        session = self._load_record(session_id, tenant_id)
        if session_id and session:
            session["pending_interaction"] = None
            session["updated_at"] = time.time()
            self._save_record(session_id, tenant_id, session)

    def add_answer(
        self,
        session_id: Optional[str],
        tenant_id: str,
        key: str,
        value: Any,
    ) -> Optional[Dict[str, Any]]:
        pending = self.get_pending_interaction(session_id, tenant_id)
        if not pending:
            return None
        pending.setdefault("answers", {})[key] = value
        session = self._load_record(session_id, tenant_id)
        if session:
            session["pending_interaction"] = pending
            session["updated_at"] = time.time()
            self._save_record(session_id, tenant_id, session)
        return pending

    def is_complete(self, session_id: Optional[str], tenant_id: str) -> bool:
        pending = self.get_pending_interaction(session_id, tenant_id)
        if not pending:
            return False
        expected_fields = pending.get("expected_fields", [])
        if not expected_fields:
            return True
        answers = pending.get("answers", {})
        return all(field in answers and str(answers[field]).strip() for field in expected_fields)

    def get_session_context(self, session_id: Optional[str], tenant_id: str) -> Dict[str, Any]:
        session = self._load_record(session_id, tenant_id)
        if not session:
            return self._default_context()
        return session.get("session_context", self._default_context())

    def merge_session_context(
        self,
        session_id: Optional[str],
        tenant_id: str,
        dataset_id: Optional[str] = None,
        resolved_terms: Optional[Dict[str, str]] = None,
        last_metric: Optional[str] = None,
        last_dimensions: Optional[list[str]] = None,
    ) -> Optional[str]:
        sid = session_id or str(uuid.uuid4())
        session = self._load_record(sid, tenant_id) or {
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "pending_interaction": None,
            "session_context": self._default_context(),
        }
        context = session.get("session_context", self._default_context())
        if resolved_terms:
            context.setdefault("resolved_terms", {}).update(resolved_terms)
        if last_metric:
            context["last_metric"] = last_metric
        if last_dimensions:
            context["last_dimensions"] = list(last_dimensions)
        session["dataset_id"] = dataset_id or session.get("dataset_id")
        session["session_context"] = context
        session["updated_at"] = time.time()
        self._save_record(sid, tenant_id, session)
        return sid


session_service = SessionService()
