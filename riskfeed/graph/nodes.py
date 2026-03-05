from __future__ import annotations

from typing import Any, Dict, List
from riskfeed.graph.state import GraphState


def intent_router_node(state: GraphState) -> GraphState:
    """
    Decide what the user is trying to do based on the message.
    """
    msg = (state.get("message") or "").lower().strip()

    if state.get("confirm_action_id"):
        state["intent"] = "confirm_attempt"
        return state

    if any(k in msg for k in ["find contractor", "recommend contractor", "shortlist", "hire contractor"]):
        state["intent"] = "match_contractors"
    elif any(k in msg for k in ["risk", "alert", "overrun", "delay"]):
        state["intent"] = "risk_check"
    elif any(k in msg for k in ["milestone", "definition of done", "dod"]):
        state["intent"] = "milestones"
    elif any(k in msg for k in ["remodel", "renov", "kitchen", "bath"]):
        state["intent"] = "project_intake"
    else:
        state["intent"] = "general"

    return state


def response_composer_node(state: GraphState) -> GraphState:
    """
    Convert intent into a stable response payload.
    """
    intent = state.get("intent", "general")
    msg = (state.get("message") or "").lower().strip()

    checklist: List[Dict[str, Any]] = []
    missing_info: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    # Confirmation attempt
    if intent == "confirm_attempt":
        out_message = (
            "Confirmation handling is not implemented yet. "
        )
        state["out_message"] = out_message
        state["out_checklist"] = checklist
        state["out_missing_info"] = missing_info
        state["out_actions"] = actions
        state["out_citations"] = citations
        state["out_debug"] = {"intent": intent} if state.get("debug_enabled") else {}
        return state

    # A simple project intake scaffold 
    if intent in {"project_intake", "match_contractors", "risk_check", "milestones"}:
        checklist = [
            {"id": "define_scope", "label": "Define the project scope", "done": False},
            {"id": "set_budget", "label": "Set a realistic budget", "done": False},
            {"id": "choose_contractors", "label": "Shortlist contractors", "done": False},
        ]

        # budget question
        if "budget" not in msg and "$" not in msg and "usd" not in msg:
            missing_info.append({"field": "budget_usd", "question": "What is your target budget range (USD)?"})

        # location question
        if " in " not in msg and "austin" not in msg and "tx" not in msg:
            missing_info.append({"field": "location", "question": "Where is the project located (city/state)?"})

        # propose a tool call
        actions.append(
            {
                "id": "action_create_project_draft_001",
                "type": "tool_call_proposed",
                "tool_name": "project.create_project_draft",
                "args": {"project_type": "remodel", "location": "unknown"},
                "requires_confirmation": False,
                "confirm_action_id": None,
            }
        )

        out_message = (
            "I can help you with that using a guided, risk-first workflow.\n"
            "Next: answer the missing questions so I can proceed safely."
        )
    else:
        out_message = (
            "Hi — I’m the RiskFeed assistant.\n"
            "Tell me what you want to do: hire a contractor, check project risks, or draft milestones."
        )

    state["out_message"] = out_message
    state["out_checklist"] = checklist
    state["out_missing_info"] = missing_info
    state["out_actions"] = actions
    state["out_citations"] = citations
    state["out_debug"] = {"intent": intent} if state.get("debug_enabled") else {}
    return state