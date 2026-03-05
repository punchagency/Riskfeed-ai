from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Literal

from riskfeed.utils.ids import new_id

Role = Literal["homeowner", "contractor"]


# Pending action is a tool call that must be confirmed before execution
@dataclass
class PendingAction:
    """
    Properties enforced:
    - expires_at (TTL)
    - single-use (once executed, cannot be executed again)
    - bound to role + session_id (RBAC + safety)
    """
    tool_name: str
    args: Dict[str, Any]
    role: Role
    session_id: str
    expires_at: datetime
    used: bool = False
    used_at: Optional[datetime] = None


# In-memory confirmation store
_PENDING: Dict[str, PendingAction] = {}

DEFAULT_TTL_SECONDS = 20 * 60  # 20 minutes


# Create a pending action
def create_pending_action(*, tool_name: str, args: Dict[str, Any], role: Role, session_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    confirm_id = new_id("confirm_")
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    _PENDING[confirm_id] = PendingAction(
        tool_name=tool_name,
        args=args,
        role=role,
        session_id=session_id,
        expires_at=expires_at,
    )
    return confirm_id


# Peek at a pending action
def peek(confirm_id: str) -> Optional[PendingAction]:
    return _PENDING.get(confirm_id)


# Consume a pending action i.e. validate + mark as used
def consume(confirm_id: str, *, role: Role, session_id: str) -> tuple[bool, str, Optional[PendingAction]]:
    action = _PENDING.get(confirm_id)
    if not action:
        return False, "Unknown confirmation id (not found).", None

    now = datetime.now(timezone.utc)

    if action.used:
        return False, "This confirmation id was already used.", None

    if now > action.expires_at:
        return False, "This confirmation id has expired.", None

    if action.role != role:
        return False, "Role mismatch: you are not allowed to confirm this action.", None

    if action.session_id != session_id:
        return False, "Session mismatch: you are not allowed to confirm this action.", None

    # Mark used
    action.used = True
    action.used_at = now
    _PENDING[confirm_id] = action

    return True, "", action