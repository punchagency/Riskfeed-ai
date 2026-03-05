from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel


class ListContractorsArgs(BaseModel):
    pass


class ContractorPublic(BaseModel):
    id: str
    name: str
    trades: List[str]
    service_area: List[str]
    badges: List[str]
    completed_jobs: int
    reviews_summary: str


class ListContractorsResult(BaseModel):
    contractors: List[ContractorPublic]


from riskfeed.tools.state_score import STORE  # import after models (cleaner for beginners)


def list_contractors(raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: contractor.list_contractors
    Returns a PUBLIC view of contractors (no private fields).
    """
    _ = ListContractorsArgs.model_validate(raw_args)

    contractors = [ContractorPublic(**c) for c in STORE.contractors]
    result = ListContractorsResult(contractors=contractors)

    return {"ok": True, "tool_name": "contractor.list_contractors", "data": result.model_dump()}