from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from riskfeed.tools.state_score import STORE


class ComputeProjectRiskArgs(BaseModel):
    project_id: str = Field(..., description="Project draft id (proj_...)")
    owner_key: str = Field(..., description="session_id placeholder (authorization check)")


class RiskDriver(BaseModel):
    category: str
    severity: str
    evidence: str


class RiskResult(BaseModel):
    project_id: str
    risk_score_0_100: int
    confidence: float
    drivers: List[RiskDriver]
    mitigations: List[str]
    missing_data: List[str]


def compute_project_risk(raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: risk.compute_project_risk
    Deterministic v0 heuristic scoring. Later replaced by ML.
    """
    args = ComputeProjectRiskArgs.model_validate(raw_args)

    proj = STORE.get_project(args.project_id)
    if not proj:
        return {"ok": False, "tool_name": "risk.compute_project_risk", "error": "Project not found"}

    # Ownership check (mock authorization)
    if proj.get("owner_key") != args.owner_key:
        return {"ok": False, "tool_name": "risk.compute_project_risk", "error": "Access denied (owner mismatch)"}

    # --- v0 scoring heuristics ---
    drivers: List[RiskDriver] = []
    mitigations: List[str] = []
    missing: List[str] = []

    score = 35  # base risk (construction is inherently risky)
    confidence = 0.75

    if not proj.get("location"):
        score += 15
        confidence -= 0.10
        missing.append("location")
        drivers.append(RiskDriver(category="Execution", severity="High", evidence="Project location is missing."))
        mitigations.append("Provide city/state so permit and contractor availability risks can be assessed.")

    if proj.get("budget_usd") is None:
        score += 15
        confidence -= 0.10
        missing.append("budget_usd")
        drivers.append(RiskDriver(category="Financial", severity="High", evidence="Budget is missing."))
        mitigations.append("Set a budget range; risk checks depend on scope-to-budget realism.")

    # Permits: remodels often trigger permits. We don’t have a permits field yet, so we mark it as missing.
    if "remodel" in (proj.get("project_type") or "").lower():
        score += 10
        confidence -= 0.05
        missing.append("permits_plan")
        drivers.append(RiskDriver(category="Compliance", severity="Medium", evidence="Permit plan not provided."))
        mitigations.append("Confirm permit requirements with the city/county and attach inspection checkpoints to milestones.")

    # Contractor chosen: not tracked yet
    if proj.get("contractor_id") is None:
        score += 10
        confidence -= 0.05
        missing.append("contractor_id")
        drivers.append(RiskDriver(category="Contractor", severity="Medium", evidence="No contractor has been shortlisted/selected."))
        mitigations.append("Shortlist contractors with relevant-job history and clear scope/change-order practices.")

    # Cap + floor
    score = max(0, min(100, score))
    confidence = max(0.30, min(0.95, confidence))

    result = RiskResult(
        project_id=args.project_id,
        risk_score_0_100=score,
        confidence=round(confidence, 2),
        drivers=drivers,
        mitigations=mitigations,
        missing_data=missing,
    )

    return {"ok": True, "tool_name": "risk.compute_project_risk", "data": result.model_dump()}