from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionData:
    session_id: str
    answers: dict[str, bool] = field(default_factory=dict)
    marking_snapshot: dict[str, Any] = field(default_factory=dict)
    current_step: int = 1
    completed_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pending_warning: str | None = None
    last_result: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, ttl_seconds: int = 24 * 3600):
        self._sessions: dict[str, SessionData] = {}
        self.ttl_seconds = ttl_seconds

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.created_at > self.ttl_seconds]
        for sid in expired:
            del self._sessions[sid]

    def create(self) -> SessionData:
        self._purge_expired()
        session_id = str(uuid.uuid4())
        data = SessionData(session_id=session_id)
        self._sessions[session_id] = data
        return data

    def get(self, session_id: str | None) -> SessionData | None:
        if not session_id:
            return None
        self._purge_expired()
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> SessionData:
        existing = self.get(session_id)
        if existing:
            return existing
        return self.create()

    def save(self, data: SessionData) -> None:
        self._sessions[data.session_id] = data

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
