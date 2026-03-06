from __future__ import annotations

from fastapi import APIRouter
from riskfeed.api.schemas import ChatRequest, ChatResponse
from riskfeed.graph.ochestrator import run_chat

from riskfeed.utils.trace import new_trace_id
trace_id = new_trace_id()

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    /chat is powered by LangGraph.
    """
    out_state = run_chat(
        role=req.role,
        message=req.message,
        session_id=req.session_id,
        confirm_action_id=req.confirm_action_id,
        debug_enabled=req.debug,
    )

    return ChatResponse(
        message=out_state.get("out_message", ""),
        role=req.role,
        checklist=out_state.get("out_checklist", []),
        missing_info=out_state.get("out_missing_info", []),
        actions=out_state.get("out_actions", []),
        citations=out_state.get("out_citations", []),
        debug=out_state.get("out_debug", {}) if req.debug else {},
    )