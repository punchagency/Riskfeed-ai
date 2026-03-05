from __future__ import annotations

from typing import Literal, Set

Role = Literal["homeowner", "contractor"]


# Which tools each role can call
ALLOWED_TOOLS: dict[Role, Set[str]] = {
    "homeowner": {
        "project.create_project_draft",
        "contractor.list_contractors",
        "bidding.send_invite",
    },
    "contractor": {
        # Contractors should NOT create homeowner projects.
        "contractor.list_contractors",
        "bidding.send_invite",  # (we allow for demo; later you might restrict)
    },
}

def is_tool_allowed(role: Role, tool_name: str) -> bool:
    return tool_name in ALLOWED_TOOLS.get(role, set())