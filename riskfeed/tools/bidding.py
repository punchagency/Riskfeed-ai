from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel, Field


# Send an invite to a contractor for a project
class SendInviteArgs(BaseModel):
    contractor_id: str = Field(..., description="e.g., c1")
    project_id: str = Field(..., description="project draft id")
    note: str = Field(default="", description="optional invite note")


# Result of sending an invite
class SendInviteResult(BaseModel):
    sent: bool
    contractor_id: str
    project_id: str


# Send an invite to a contractor for a project
def send_invite(raw_args: Dict[str, Any]) -> Dict[str, Any]:
    args = SendInviteArgs.model_validate(raw_args)
    result = SendInviteResult(sent=True, contractor_id=args.contractor_id, project_id=args.project_id)
    return {"ok": True, "tool_name": "bidding.send_invite", "data": result.model_dump()}