from __future__ import annotations

from typing import Any, Callable, Dict

from riskfeed.tools.project import create_project_draft
from riskfeed.tools.contractor import list_contractors

ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]

REGISTRY: Dict[str, ToolFn] = {
    "project.create_project_draft": create_project_draft,
    "contractor.list_contractors": list_contractors,
}


def get_tool(tool_name: str) -> ToolFn:
    if tool_name not in REGISTRY:
        raise KeyError(f"Unknown tool: {tool_name}")
    return REGISTRY[tool_name]