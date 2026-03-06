from __future__ import annotations

from typing import Any, Callable, Dict

from riskfeed.tools.project import create_project_draft
from riskfeed.tools.contractor import list_contractors
from riskfeed.tools.bidding import send_invite

from riskfeed.tools.debug_tools import crash_tool
from riskfeed.tools.risk import compute_project_risk

ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]

REGISTRY: Dict[str, ToolFn] = {
    "project.create_project_draft": create_project_draft,
    "contractor.list_contractors": list_contractors,
    "bidding.send_invite": send_invite,
    "debug.crash_tool": crash_tool,
    "risk.compute_project_risk": compute_project_risk,
}

def get_tool(tool_name: str) -> ToolFn:
    if tool_name not in REGISTRY:
        raise KeyError(f"Unknown tool: {tool_name}")
    return REGISTRY[tool_name]