from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional


class SessionService:
    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_or_update_pending_interaction(
        self,
        session_id: Optional[str],
        tenant_id: str,
        dataset_id: Optional[str],
        interaction: Dict[str, Any],
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        questions = interaction.get("questions", [])
        expected_fields = interaction.get("expected_fields") or [
            question["key"] for question in questions if question.get("key")
        ]
        self._sessions[sid] = {
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
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
        return sid

    def get_pending_interaction(
        self,
        session_id: Optional[str],
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if not session or session.get("tenant_id") != tenant_id:
            return None
        return session.get("pending_interaction")

    def clear_pending_interaction(self, session_id: Optional[str], tenant_id: str) -> None:
        if not session_id:
            return
        session = self._sessions.get(session_id)
        if session and session.get("tenant_id") == tenant_id:
            session["pending_interaction"] = None
            session["updated_at"] = time.time()

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
        session = self._sessions.get(session_id)
        if session:
            session["updated_at"] = time.time()
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


session_service = SessionService()
