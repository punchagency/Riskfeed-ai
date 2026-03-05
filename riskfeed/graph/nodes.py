from __future__ import annotations

import re
from typing import Any, Dict, List

from riskfeed.graph.state import GraphState
from riskfeed.tools.registry import get_tool


def intent_router_node(state: GraphState) -> GraphState:
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


def _extract_location(message: str) -> str | None:
    m = re.search(r"\bin\s+([a-zA-Z\s]{2,30})", message)
    if not m:
        return None
    return m.group(1).strip()


def _extract_budget(message: str) -> int | None:
    """
    Extract basic budget numbers like:
    - $25000
    - 25000 USD
    - budget 25000
    """
    m = re.search(r"(\$?\s?\d{4,6})", message)
    if not m:
        return None
    raw = m.group(1).replace("$", "").strip()
    try:
        return int(raw)
    except Exception:
        return None


def planner_node(state: GraphState) -> GraphState:
    """
    Planner decides:
    1) What info is missing (so we can ask the user)
    2) What tools to call (if we have enough info)
    """
    msg = (state.get("message") or "").strip()
    intent = state.get("intent", "general")
    session_id = state.get("session_id") or "anon_session"

    extracted: Dict[str, Any] = {}
    missing_info: List[Dict[str, Any]] = []
    planned_tool_calls: List[Dict[str, Any]] = []

    # For these intents we want project context
    if intent in {"project_intake", "match_contractors"}:
        location = _extract_location(msg) or ""
        budget = _extract_budget(msg)

        # very simple project type guess
        project_type = "kitchen remodel" if "kitchen" in msg.lower() else "remodel"

        extracted["project_type"] = project_type
        extracted["location"] = location
        if budget is not None:
            extracted["budget_usd"] = budget

        if not location:
            missing_info.append({"field": "location", "question": "Where is the project located (city/state)?"})
        if budget is None:
            missing_info.append({"field": "budget_usd", "question": "What is your target budget range (USD)?"})

        # If no missing info, we can create a project draft (tool-first)
        if not missing_info:
            planned_tool_calls.append(
                {
                    "tool_name": "project.create_project_draft",
                    "args": {
                        "project_type": project_type,
                        "location": location,
                        "owner_key": session_id,  # placeholder owner until we add user_id
                    },
                }
            )

        # If they asked specifically to find contractors and we have enough info, we also list contractors
        if intent == "match_contractors" and not missing_info:
            planned_tool_calls.append(
                {"tool_name": "contractor.list_contractors", "args": {}}
            )

    state["extracted"] = extracted
    state["missing_info"] = missing_info
    state["planned_tool_calls"] = planned_tool_calls
    state["tool_results"] = []
    return state


def tool_executor_node(state: GraphState) -> GraphState:
    """
    Execute planned tools and store results
    """
    results: List[Dict[str, Any]] = []

    for call in state.get("planned_tool_calls", []):
        tool_name = call["tool_name"]
        args = call.get("args", {})

        tool_fn = get_tool(tool_name)
        tool_out = tool_fn(args)

        results.append(tool_out)

    state["tool_results"] = results
    return state


def response_composer_node(state: GraphState) -> GraphState:
    """
    Build the stable response shape, but now grounded in tool results.

    This is where the chatbot turns raw tool outputs into helpful text.
    """
    intent = state.get("intent", "general")
    msg = (state.get("message") or "").lower().strip()

    checklist: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    # Confirmation still not implemented
    if intent == "confirm_attempt":
        state["out_message"] = (
            "Confirmation handling isn't implemented yet "
            "For now, continue without confirm_action_id."
        )
        state["out_checklist"] = []
        state["out_missing_info"] = []
        state["out_actions"] = []
        state["out_citations"] = []
        state["out_debug"] = {"intent": intent} if state.get("debug_enabled") else {}
        return state

    # Basic checklist (same as before)
    if intent in {"project_intake", "match_contractors", "risk_check", "milestones"}:
        checklist = [
            {"id": "define_scope", "label": "Define the project scope", "done": False},
            {"id": "set_budget", "label": "Set a realistic budget", "done": False},
            {"id": "choose_contractors", "label": "Shortlist contractors", "done": False},
        ]

    # If missing info, ask the user instead of calling tools (tool-first, safe)
    missing_info = state.get("missing_info", [])
    if missing_info:
        state["out_message"] = (
            "I can help you with that using a guided, risk-first workflow.\n"
            "Before I proceed, I need these details:"
        )
        state["out_checklist"] = checklist
        state["out_missing_info"] = missing_info
        state["out_actions"] = []
        state["out_citations"] = citations
        state["out_debug"] = {
            "intent": intent,
            "tool_calls": [],
            "retrieval": {"hits": 0},
        } if state.get("debug_enabled") else {}
        return state

    # Use tool results (grounded output)
    tool_results = state.get("tool_results", [])
    created_project_id = None
    contractors = []

    for r in tool_results:
        if r.get("ok") and r.get("tool_name") == "project.create_project_draft":
            created_project_id = r["data"]["project_id"]

        if r.get("ok") and r.get("tool_name") == "contractor.list_contractors":
            contractors = r["data"]["contractors"]

    # Compose message
    lines: List[str] = []
    if created_project_id:
        lines.append(f"Project draft created: {created_project_id}")

    if contractors:
        lines.append("Here are available contractors (mock data for now):")
        for c in contractors[:3]:
            lines.append(f"- {c['name']} — trades: {', '.join(c['trades'])}")

    if not lines:
        lines.append(
            "Hi — I’m the RiskFeed assistant.\n"
            "Tell me what you want to do: hire a contractor, check project risks, or draft milestones."
        )

    state["out_message"] = "\n".join(lines)
    state["out_checklist"] = checklist
    state["out_missing_info"] = []
    state["out_actions"] = actions
    state["out_citations"] = citations
    state["out_debug"] = {
        "intent": intent,
        "tool_calls": state.get("planned_tool_calls", []),
        "retrieval": {"hits": 0},
    } if state.get("debug_enabled") else {}

    return state