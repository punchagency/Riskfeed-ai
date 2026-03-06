from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class SessionData:
    """
    In-memory session store.

    Think of this like a temporary "brain" for the chatbot:
    - It remembers what the user already said in this session.
    - It caches results of write actions to prevent duplicates (idempotency).
    """
    session_id: str
    memory: Dict[str, Any] = field(default_factory=dict)
    idempotency_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


# Global in-memory sessions (Phase 6 simplicity)
_SESSIONS: Dict[str, SessionData] = {}


def get_session(session_id: str) -> SessionData:
    """
    Get or create a session.
    """
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = SessionData(session_id=session_id)
    s = _SESSIONS[session_id]
    s.touch()
    return s


def make_idempotency_key(session_id: str, tool_name: str, args: Dict[str, Any]) -> str:
    """
    Creates a stable key for a tool call.
    If the same tool call repeats in the same session, we can reuse the result.

    Why JSON dumps + sort_keys:
    - It ensures {"a":1,"b":2} and {"b":2,"a":1} hash the same.
    """
    payload = json.dumps({"session_id": session_id, "tool_name": tool_name, "args": args}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_result(session: SessionData, idem_key: str) -> Optional[Dict[str, Any]]:
    return session.idempotency_cache.get(idem_key)


def set_cached_result(session: SessionData, idem_key: str, result: Dict[str, Any]) -> None:
    session.idempotency_cache[idem_key] = result
    session.touch()