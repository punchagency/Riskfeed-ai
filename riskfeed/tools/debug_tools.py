# riskfeed/tools/debug_tools.py
from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel


class CrashArgs(BaseModel):
    pass


def crash_tool(raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Always raises an exception (for resilience tests).
    """
    _ = CrashArgs.model_validate(raw_args)
    raise RuntimeError("Intentional crash for testing")