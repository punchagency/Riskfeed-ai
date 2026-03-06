from __future__ import annotations

import re
from typing import Any, Dict, List

from riskfeed.graph.state import GraphState
from riskfeed.tools.registry import get_tool

from riskfeed.auth.rbac import is_tool_allowed
from riskfeed.auth.sensitive import requires_confirmation
from riskfeed.auth.confirmations import create_pending_action, consume

from riskfeed.retrieval.tfidf import RETRIEVER

from riskfeed.graph.session import get_session, make_idempotency_key, get_cached_result, set_cached_result

from riskfeed.utils.logging import log_event

# Session load node loads session memory into graph state before we do intent routing/planning.
def session_load_node(state: GraphState) -> GraphState:
    """
    This is how the chatbot "remembers" what the user already said.
    """
    session_id = state.get("session_id") or "anon_session"
    state["session_id"] = session_id

    session = get_session(session_id)
    state["session_memory"] = dict(session.memory)  # copy for safety
    state["current_project_id"] = session.memory.get("current_project_id")

    return state


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
    # Permits/inspections are informational; answer directly using retrieval
    # rather than forcing project-intake fields like budget/location.
    elif ("permit" in msg) or ("inspection" in msg):
        state["intent"] = "general"
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

    if "crash tool" in msg.lower():
        planned_tool_calls.append({"tool_name": "debug.crash_tool", "args": {}})

    if intent == "confirm":
        state["extracted"] = {}
        state["missing_info"] = []
        state["planned_tool_calls"] = []
        state["tool_results"] = []
        return state   

    # Project related
    if intent in {"project_intake", "match_contractors"}:
        session_mem = state.get("session_memory", {})

        location = _extract_location(msg) or session_mem.get("location") or ""
        budget = _extract_budget(msg)
        if budget is None:
            budget = session_mem.get("budget_usd")
        project_type = "kitchen remodel" if "kitchen" in msg.lower() else (session_mem.get("project_type") or "remodel")

        extracted["project_type"] = project_type
        extracted["location"] = location
        if budget is not None:
            extracted["budget_usd"] = budget

        if not location:
            missing_info.append({"field": "location", "question": "Where is the project located (city/state)?"})
        if budget is None:
            missing_info.append({"field": "budget_usd", "question": "What is your target budget range (USD)?"})

        if not missing_info:
            existing_project_id = state.get("current_project_id")
            if existing_project_id:
                extracted["project_id"] = existing_project_id
            else:
                planned_tool_calls.append({
                    "tool_name": "project.create_project_draft",
                    "args": {"project_type": project_type, "location": location, "owner_key": session_id},
                })

        if intent == "match_contractors" and not missing_info:
            planned_tool_calls.append({"tool_name": "contractor.list_contractors", "args": {}})

    # Risk check flow
    if intent == "risk_check":
        m = re.search(r"\b(proj_[a-f0-9]+)\b", msg.lower())
        project_id = m.group(1) if m else state.get("current_project_id")

        if not project_id:
            missing_info.append(
                {
                    "field": "project_id",
                    "question": "Which project draft id? (looks like proj_...)",
                }
            )
        else:
            planned_tool_calls.append(
                {
                    "tool_name": "risk.compute_project_risk",
                    "args": {"project_id": project_id, "owner_key": session_id},
                }
            )
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


WRITE_TOOLS = {"project.create_project_draft", "bidding.send_invite"}

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
        try:
            out = tool_fn(action.args)
        except Exception as e:
            out = {
                "ok": False,
                "tool_name": action.tool_name,
                "error": f"Tool raised exception: {type(e).__name__}",
            }
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

        # Idempotency check
        session = get_session(session_id)

        idem_key = None
        if tool_name in WRITE_TOOLS:
            idem_key = make_idempotency_key(session_id, tool_name, args)
            cached = get_cached_result(session, idem_key)
            if cached:
                results.append(cached)
                continue


        tool_fn = get_tool(tool_name)
        try:
            out = tool_fn(args)
        except Exception as e:
            out = {
                "ok": False,
                "tool_name": tool_name,
                "error": f"Tool raised exception: {type(e).__name__}",
            }

        # cache the result
        if idem_key and out.get("ok"):
            set_cached_result(session, idem_key, out)

        results.append(out)
    log_event(
        "tools.executed",
        {
            "trace_id": state.get("trace_id"),
            "session_id": session_id,
            "role": role,
            "results": [{"tool": r.get("tool_name"), "ok": r.get("ok")} for r in results],
        },
    )
    state["tool_results"] = results
    return state

# Session saver node saves the session memory
def session_save_node(state: GraphState) -> GraphState:
    """
    Saves useful info back into session memory after we have results.
    """
    session_id = state.get("session_id") or "anon_session"
    session = get_session(session_id)

    extracted = state.get("extracted", {}) or {}

    # Save extracted fields if present
    for k in ["location", "budget_usd", "project_type"]:
        if extracted.get(k):
            session.memory[k] = extracted[k]

    # If tool created a project draft, store it as current_project_id
    for r in state.get("tool_results", []):
        if r.get("ok") and r.get("tool_name") == "project.create_project_draft":
            project_id = r["data"]["project_id"]
            session.memory["current_project_id"] = project_id

    session.touch()
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
            "trace_id": state.get("trace_id"),
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
            "trace_id": state.get("trace_id"),
        } if state.get("debug_enabled") else {}
        return state

    created_project_id = None
    contractors = []
    risk_report = None

    for r in tool_results:
        if r.get("ok") and r.get("tool_name") == "project.create_project_draft":
            created_project_id = r["data"]["project_id"]
        if r.get("ok") and r.get("tool_name") == "contractor.list_contractors":
            contractors = r["data"]["contractors"]
        if r.get("ok") and r.get("tool_name") == "bidding.send_invite":
            lines.append("Invite sent successfully (mock).")
        if r.get("ok") and r.get("tool_name") == "risk.compute_project_risk":
            risk_report = r["data"]

    existing_project_id = state.get("current_project_id")
    if existing_project_id and not created_project_id:
        lines.append(f"Project draft already exists: {existing_project_id}")

    if risk_report:
        lines.append(f"Risk Score (0-100): {risk_report['risk_score_0_100']}")
        lines.append(f"Confidence: {risk_report['confidence']}")
        lines.append("")
        lines.append("Risk drivers:")
        for driver in risk_report.get("drivers", []):
            lines.append(f"- {driver['category']}: {driver['severity']} ({driver['evidence']})")
        lines.append("")
        lines.append("Recommended mitigations:")
        for mitigation in risk_report.get("mitigations", []):
            lines.append(f" - {mitigation}")
        if risk_report["missing_data"]:
            lines.append("")
            lines.append("Missing data (to improve accuracy):")
            for x in risk_report["missing_data"]:
                lines.append(f" - {x}")

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
    debug_payload: Dict[str, Any] = {}
    if state.get("debug_enabled"):
        debug_payload = {
            "intent": intent,
            "tool_calls": state.get("planned_tool_calls", []),
            "retrieval": state.get("retrieval_meta", {"hits": 0}),
            "trace_id": state.get("trace_id"),
        }
    state["out_debug"] = debug_payload
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

# Verifier node checks if the response is safe and consistent
def verifier_node(state: GraphState) -> GraphState:
    """Checks if the response is safe + consistent"""
    errors: List[str] = []

    # Rule 0: input message must exist (otherwise trigger repair fallback)
    in_message = state.get("message", "")
    if not in_message or not in_message.strip():
        errors.append("input message is empty")

    # Rule 1: message must exist
    out_message = state.get("out_message", "")
    if not out_message or not out_message.strip():
        errors.append("out_message is empty")

    # Rule 2: if actions require confirmation, confirm_action_id must exist
    for action in state.get("out_actions", []):
        if action.get("requires_confirmation") and not action.get("confirm_action_id"):
            errors.append("action requires confirmation but confirm_action_id missing")

    # Rule 3: if we executed a sensitive tool, it must have come from confirmation path
    # In Phase 3, sensitive tools should only execute when confirm_action_id was provided.
    confirm_used = bool(state.get("confirm_action_id"))
    for r in state.get("tool_results", []):
        tname = r.get("tool_name", "")
        # Pending-confirmation results are not executions; they are proposals.
        if tname == "bidding.send_invite" and r.get("ok") and not confirm_used and not r.get("pending_confirmation"):
            errors.append("sensitive tool executed without confirmation")

    # Rule 4: if we say "based on knowledge base", citations should exist
    if "knowledge base" in out_message.lower():
        if not state.get("out_citations"):
            errors.append("message references knowledge base but citations are empty")

    state["verification_errors"] = errors
    state["verification_ok"] = len(errors) == 0
    return state

#  Repair node repairs the output into a safe and consistent fallback
def repair_node(state: GraphState) -> GraphState:
    """Repairs the output into a safe and consistent fallback"""
    errors = state.get("verification_errors", [])

    # Basic safe fallback message
    safe_lines = [
        "I hit a consistency check and paused to keep things safe.",
        "Here’s what I can do next:",
        "- Ask you for missing info",
        "- Propose actions (with confirmations where required)",
        "- Provide guidance grounded in the knowledge base (with citations)",
    ]
    safe_lines.append("")
    safe_lines.append("Detected issues:")
    for e in errors:
        safe_lines.append(f"- {e}")

    # Clear unsafe actions; keep citations if present
    state["out_message"] = "\n".join(safe_lines)
    state["out_actions"] = []  # safest repair
    state["out_missing_info"] = state.get("out_missing_info", [])
    state["verification_ok"] = True  # repaired response is now safe
    return state