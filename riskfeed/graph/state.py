from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

Role = Literal["homeowner", "contractor"]


class GraphState(TypedDict, total=False):
    """
    This is the single object that flows through LangGraph.
    """

    # request inputs
    role: Role
    message: str
    session_id: Optional[str]
    confirm_action_id: Optional[str]
    debug_enabled: bool

    # internal routing
    intent: str

    # outputs (we will map these into ChatResponse)
    out_message: str
    out_checklist: List[Dict[str, Any]]
    out_missing_info: List[Dict[str, Any]]
    out_actions: List[Dict[str, Any]]
    out_citations: List[Dict[str, Any]]
    out_debug: Dict[str, Any]