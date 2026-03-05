from __future__ import annotations

from fastapi import APIRouter
from .schemas import (
    Action,
    ChatRequest,
    ChatResponse,
    ChecklistItem,
    MissingInfo,
)

router = APIRouter()

@router.get("/health")
def health() -> dict:
    """Health check endpoint"""
    return {"status": "ok"}

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Chat endpoint"""

    msg = req.message.lower().strip()

    if req.confirm_action_id:
        return ChatResponse(
            message=(
                "You have confirmed the action."
            ),
            role=req.role,
            debug={"intent": "confirm_attempt" if req.debug else {}}
        )
        
    # missing info
    missing_info: list[MissingInfo] = []
    checklist: list[ChecklistItem] = []
    actions: list[Action] = []

    # This is a simple heuristic to demonstrate how missing-info work
    if "remodel" in msg or "renov" in msg or "kitchen" in msg or "bath" in msg:
        checklist = [
            ChecklistItem(id="define_scope", label="Define the project scope", done=False),
            ChecklistItem(id="set_budget", label="Set a realistic budget", done=False),
            ChecklistItem(id="choose_contractor", label="Shortlist contractors", done=False),
        ]

        # ask for budget if not present
        if "budget" not in msg and "$" not in msg and "usd" not in msg:
            missing_info.append(MissingInfo(field="budget", question="What is the budget for the project?"))

        # propose a "tool-call"
        actions.append(
            Action(
                id="project_001",
                tool_name="project.project_draft",
                args={
                    "project_type": "kitchen remodel" if "kitchen" in msg else "remodel",
                    "location": "unknown",
                },
                requires_confirmation=False,
                confirm_action_id=None,                
            )
        )
        message_out = (
            "I can help you with that. I'll guide you step-by-step.\n"
            "Next: answer the missing questions so I can proceed safely."
        )
    else:
        message_out = (
            "Hi - I'm the RiskFeed Assistant.\n"
            "Tell me what you want to do: hire a contractor, check project risks, or draft milesones"
        )
    debug_block = {"intent": "initial_greeting"} if req.debug else {}

    return ChatResponse(
        message=message_out,
        role=req.role,
        checklist=checklist,
        missing_info=missing_info,
        actions=actions,
        debug=debug_block,
    )



