from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

Role = Literal["homeowner", "contractor"]


class GraphState(TypedDict, total=False):
    # request inputs
    role: Role
    message: str
    session_id: Optional[str]
    confirm_action_id: Optional[str]
    debug_enabled: bool

    # internal routing
    intent: str

    # planning + execution
    extracted: Dict[str, Any]
    missing_info: List[Dict[str, Any]]
    planned_tool_calls: List[Dict[str, Any]]   # [{tool_name: str, args: {...}}]
    tool_results: List[Dict[str, Any]]         # tool outputs in order

    # outputs
    out_message: str
    out_checklist: List[Dict[str, Any]]
    out_missing_info: List[Dict[str, Any]]
    out_actions: List[Dict[str, Any]]
    out_citations: List[Dict[str, Any]]
    out_debug: Dict[str, Any]