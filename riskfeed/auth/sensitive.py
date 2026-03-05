from __future__ import annotations

SENSITIVE_TOOLS = {
    # Anything that changes workflow or resembles money movement must be confirmed.
    "bidding.send_invite",
    # later: payments.release_funds, milestone.approve_milestone, etc.
}

def requires_confirmation(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS