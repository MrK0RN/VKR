from __future__ import annotations

import secrets
import time
from typing import Any

from app import config


def _empty_session() -> dict[str, Any]:
    return {
        "answers": {},
        "marking": {"places": {}, "scores": {"score_hyper": 0.0, "score_atrophic": 0.0}},
        "step": 1,
        "warnings_ack": [],
        "warnings_shown": [],
        "pending_warning": None,
        "completed_sections": [],
        "created_at": time.time(),
    }


class SessionStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self) -> tuple[str, dict[str, Any]]:
        session_id = secrets.token_urlsafe(16)
        session = _empty_session()
        self._store[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> dict[str, Any] | None:
        session = self._store.get(session_id)
        if not session:
            return None
        if time.time() - session.get("created_at", 0) > config.SESSION_TTL_SECONDS:
            del self._store[session_id]
            return None
        return session

    def save(self, session_id: str, session: dict[str, Any]) -> None:
        self._store[session_id] = session

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def clear_all(self) -> None:
        """Для тестов и административного сброса in-memory хранилища."""
        self._store.clear()


session_store = SessionStore()
