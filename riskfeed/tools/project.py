from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from riskfeed.tools.state_score import STORE


class CreateProjectDraftArgs(BaseModel):
    project_type: str = Field(..., description="e.g., kitchen remodel")
    location: str = Field(..., description="e.g., Austin, TX")
    owner_key: str = Field(..., description="temporary owner identifier (session_id for now)")
    budget_usd: Optional[int] = Field(default=None, description="optional budget in USD")


class CreateProjectDraftResult(BaseModel):
    project_id: str


def create_project_draft(raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: project.create_project_draft

    Validate inputs using Pydantic to keep tool contracts stable.
    """
    args = CreateProjectDraftArgs.model_validate(raw_args)
    project_id = STORE.create_project_draft(
        project_type=args.project_type,
        location=args.location,
        owner_key=args.owner_key,
    )
    result = CreateProjectDraftResult(project_id=project_id)
    return {"ok": True, "tool_name": "project.create_project_draft", "data": result.model_dump()}