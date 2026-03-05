from __future__ import annotations

import re
from typing import Any, Dict, List

from riskfeed.graph.state import GraphState
from riskfeed.tools.registry import get_tool

from riskfeed.auth.rbac import is_tool_allowed
from riskfeed.auth.sensitive import requires_confirmation
from riskfeed.auth.confirmations import create_pending_action, consume

from riskfeed.retrieval.tfidf import RETRIEVER


# Intent router node
def intent_router_node(state: GraphState) -> GraphState:
    msg = (state.get("message") or "").lower().strip()

    # If confirm_action_id exists, we are in confirm flow
    if state.get("confirm_action_id"):
        state["intent"] = "confirm"
        return state

    if any(k in msg for k in ["invite", "send invite"]):
        state["intent"] = "invite_contractor"
    elif any(k in msg for k in ["find contractor", "recommend contractor", "shortlist", "hire contractor"]):
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

# Extract location from message
def _extract_location(message: str) -> str | None:
    m = re.search(r"\bin\s+([a-zA-Z\s]{2,30})", message)
    if not m:
        return None
    return m.group(1).strip()

# Extract budget from message
def _extract_budget(message: str) -> int | None:
    m = re.search(r"(\$?\s?\d{4,6})", message)
    if not m:
        return None
    raw = m.group(1).replace("$", "").strip()
    try:
        return int(raw)
    except Exception:
        return None

# Extract contractor id from message
def _extract_contractor_id(message: str) -> str | None:
    m = re.search(r"\b(c\d+)\b", message.lower())
    return m.group(1) if m else None

# Planner node decides missing_info + planned_tool_calls
def planner_node(state: GraphState) -> GraphState:
    intent = state.get("intent", "general")
    msg = (state.get("message") or "").strip()
    session_id = state.get("session_id") or "anon_session"

    extracted: Dict[str, Any] = {}
    missing_info: List[Dict[str, Any]] = []
    planned_tool_calls: List[Dict[str, Any]] = []

    if intent == "confirm":
        state["extracted"] = {}
        state["missing_info"] = []
        state["planned_tool_calls"] = []
        state["tool_results"] = []
        return state

    # Project related
    if intent in {"project_intake", "match_contractors"}:
        location = _extract_location(msg) or ""
        budget = _extract_budget(msg)
        project_type = "kitchen remodel" if "kitchen" in msg.lower() else "remodel"

        extracted["project_type"] = project_type
        extracted["location"] = location
        if budget is not None:
            extracted["budget_usd"] = budget

        if not location:
            missing_info.append({"field": "location", "question": "Where is the project located (city/state)?"})
        if budget is None:
            missing_info.append({"field": "budget_usd", "question": "What is your target budget range (USD)?"})

        if not missing_info:
            planned_tool_calls.append(
                {
                    "tool_name": "project.create_project_draft",
                    "args": {"project_type": project_type, "location": location, "owner_key": session_id},
                }
            )

        if intent == "match_contractors" and not missing_info:
            planned_tool_calls.append({"tool_name": "contractor.list_contractors", "args": {}})

    # Invite flow (requires a project_id and contractor_id)
    if intent == "invite_contractor":
        contractor_id = _extract_contractor_id(msg)
        # naive project id extraction: look for proj_... in the message
        m = re.search(r"\b(proj_[a-f0-9]+)\b", msg.lower())
        project_id = m.group(1) if m else None

        if not contractor_id:
            missing_info.append({"field": "contractor_id", "question": "Which contractor? (use id like c1 for now)"})
        if not project_id:
            missing_info.append({"field": "project_id", "question": "Which project draft id? (looks like proj_...)"})

        if not missing_info:
            planned_tool_calls.append(
                {
                    "tool_name": "bidding.send_invite",
                    "args": {"contractor_id": contractor_id, "project_id": project_id, "note": ""},
                }
            )

    state["extracted"] = extracted
    state["missing_info"] = missing_info
    state["planned_tool_calls"] = planned_tool_calls
    state["tool_results"] = []
    return state


# Tool executor node enforces RBAC + confirmation gates
def tool_executor_node(state: GraphState) -> GraphState:
    role = state.get("role")
    session_id = state.get("session_id") or "anon_session"
    confirm_id = state.get("confirm_action_id")

    results: List[Dict[str, Any]] = []

    # Confirm flow: execute only the confirmed pending action
    if confirm_id:
        ok, err, action = consume(confirm_id, role=role, session_id=session_id)
        if not ok:
            state["tool_results"] = [{"ok": False, "tool_name": "confirm", "error": err}]
            return state

        # RBAC check again before execution (extra safety)
        if not is_tool_allowed(role, action.tool_name):
            state["tool_results"] = [{"ok": False, "tool_name": action.tool_name, "error": "RBAC denied"}]
            return state

        tool_fn = get_tool(action.tool_name)
        out = tool_fn(action.args)
        results.append(out)
        state["tool_results"] = results
        return state

    # Normal execution flow
    for call in state.get("planned_tool_calls", []):
        tool_name = call["tool_name"]
        args = call.get("args", {})

        # RBAC
        if not is_tool_allowed(role, tool_name):
            results.append({"ok": False, "tool_name": tool_name, "error": "RBAC denied"})
            continue

        # Confirmation gate for sensitive tools
        if requires_confirmation(tool_name):
            confirm_action_id = create_pending_action(
                tool_name=tool_name,
                args=args,
                role=role,
                session_id=session_id,
            )
            results.append(
                {
                    "ok": True,
                    "tool_name": tool_name,
                    "pending_confirmation": True,
                    "confirm_action_id": confirm_action_id,
                    "args": args,
                }
            )
            continue

        tool_fn = get_tool(tool_name)
        out = tool_fn(args)
        results.append(out)

    state["tool_results"] = results
    return state


# Response composer node composes the stable API response e.g. RBAC errors, pending confirmations actions
def response_composer_node(state: GraphState) -> GraphState:
    intent = state.get("intent", "general")
    missing_info = state.get("missing_info", [])

    checklist: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = state.get("retrieval_citations", [])

    if intent in {"project_intake", "match_contractors", "risk_check", "milestones", "invite_contractor"}:
        checklist = [
            {"id": "define_scope", "label": "Define the project scope", "done": False},
            {"id": "set_budget", "label": "Set a realistic budget", "done": False},
            {"id": "choose_contractors", "label": "Shortlist contractors", "done": False},
        ]

    if missing_info:
        state["out_message"] = (
            "Before I proceed safely, I need these details:"
        )
        state["out_checklist"] = checklist
        state["out_missing_info"] = missing_info
        state["out_actions"] = []
        state["out_citations"] = citations
        state["out_debug"] = {
            "intent": intent,
            "tool_calls": state.get("planned_tool_calls", []),
            "retrieval": state.get("retrieval_meta", {"hits": 0}),
        } if state.get("debug_enabled") else {}
        return state

    tool_results = state.get("tool_results", [])
    lines: List[str] = []

    # Handle RBAC/tool errors
    for r in tool_results:
        if r.get("ok") is False:
            lines.append(f"{r.get('tool_name')}: {r.get('error')}")

    # Handle pending confirmations (proposed actions)
    for r in tool_results:
        if r.get("pending_confirmation"):
            cid = r["confirm_action_id"]
            tname = r["tool_name"]
            lines.append(f"Action requires confirmation: {tname}")
            lines.append("Reply with confirm_action_id to proceed.")
            actions.append(
                {
                    "id": cid,
                    "type": "tool_call_proposed",
                    "tool_name": tname,
                    "args": r.get("args", {}),
                    "requires_confirmation": True,
                    "confirm_action_id": cid,
                }
            )

    # If there are pending confirmations, we stop here (don’t mix with other outputs)
    if actions:
        state["out_message"] = "\n".join(lines)
        state["out_checklist"] = checklist
        state["out_missing_info"] = []
        state["out_actions"] = actions
        state["out_citations"] = citations
        state["out_debug"] = {
            "intent": intent,
            "tool_calls": state.get("planned_tool_calls", []),
            "retrieval": state.get("retrieval_meta", {"hits": 0}),
        } if state.get("debug_enabled") else {}
        return state

    created_project_id = None
    contractors = []

    for r in tool_results:
        if r.get("ok") and r.get("tool_name") == "project.create_project_draft":
            created_project_id = r["data"]["project_id"]
        if r.get("ok") and r.get("tool_name") == "contractor.list_contractors":
            contractors = r["data"]["contractors"]
        if r.get("ok") and r.get("tool_name") == "bidding.send_invite":
            lines.append("Invite sent successfully (mock).")

    if created_project_id:
        lines.append(f"Project draft created: {created_project_id}")

    if contractors:
        lines.append("Here are available contractors (mock data for now):")
        for c in contractors[:3]:
            lines.append(f"- {c['name']} — trades: {', '.join(c['trades'])}")

    # If there are citations and no lines, add them to the output
    if citations and not lines:
        titles = [c["title"] for c in citations]
        lines.append("Here's what matters based on our RiskFeed knowledge base:")
        # Turn the snippets into short bullets 
        for c in citations[:2]:
            lines.append(f"- {c['title']}: {c['snippet']}")
        lines.append("If you tell me your project type and city/state, I can tailor the guidance and risk checklist.")

    # If no lines, default message
    if not lines:
        lines.append(
            "Hi — I’m the RiskFeed assistant.\n"
            "Tell me what you want to do: hire a contractor, check project risks, or draft milestones."
        )

    state["out_message"] = "\n".join(lines)
    state["out_checklist"] = checklist
    state["out_missing_info"] = []
    state["out_actions"] = []
    state["out_citations"] = citations
    state["out_debug"] = {
        "intent": intent,
        "tool_calls": state.get("planned_tool_calls", []),
        "retrieval": state.get("retrieval_meta", {"hits": 0}),
    } if state.get("debug_enabled") else {}

    return state

# Retrieval node uses TF-IDF to find relevant documents
def retrieval_node(state: GraphState) -> GraphState:
    """Retrieve local knowledge for grounding + citations"""

    # Get the query from the state
    query = state.get("message", "")
    citations, meta = RETRIEVER.retrieve(query)

    state["retrieval_citations"] = citations
    state["retrieval_meta"] = meta
    return state