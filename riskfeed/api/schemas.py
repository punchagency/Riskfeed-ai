from __future__ import annotations

from ctypes import SetPointerType
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Role = Literal["homeowner", "contractor"]

class ChatRequest(BaseModel):
    """
    Request schema for the /chat endpoint.
    """
    role: Role
    message: str
    session_id: Optional[str] = None
    confirm_action_id: Optional[str] = None
    debug: bool = False


class ChecklistItem(BaseModel):
    """A single item in the checklist"""
    id: str
    label: str
    done: bool = False

class MissingInfo(BaseModel):
    """A list of items that are missing from the conversation"""
    field: str
    question: str

class Action(BaseModel):
    """A single action that the user can take"""
    id: str
    type: Literal["tol_call_proposed"] = "tool_call_proposed"
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)

    # requires_confirmation: bool = False

    confirm_action_id: Optional[str] = None

class Citation(BaseModel):
    """A single citation from the knowledge base"""
    source_id: str
    title: str
    snippet: str
    uri: str

class ChatDebug(BaseModel):
    """Debug information for the chat"""
    intent: str = "unknown"
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval: Dict[str, Any] = Field(default_factory=lambda: {"hits": 0})

class ChatResponse(BaseModel):
    """This is the stable response shape for the /chat endpoint."""
    message: str
    role: Role

    checklist: List[ChecklistItem] = Field(default_factory=list)
    missing_info: List[MissingInfo] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)

    debug: Dict[str, Any] = Field(default_factory=dict)