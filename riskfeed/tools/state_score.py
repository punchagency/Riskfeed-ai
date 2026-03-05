from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from riskfeed.utils.ids import new_id


@dataclass
class InMemoryStore:
    """
    This is MOCK database.
    """
    projects: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    contractors: List[Dict[str, Any]] = field(default_factory=list)

    def seed_contractors(self) -> None:
        """
        Seed with a few contractors so we can test tool-first flows.
        """
        self.contractors = [
            {
                "id": "c1",
                "name": "Lone Star Kitchens",
                "trades": ["kitchen remodel", "cabinetry"],
                "service_area": ["Austin, TX", "Round Rock, TX"],
                "badges": ["RiskFeed Certified"],
                "completed_jobs": 42,
                "reviews_summary": "Strong communication and quality.",
            },
            {
                "id": "c2",
                "name": "BlueHammer Renovations",
                "trades": ["bathroom remodel", "general remodel"],
                "service_area": ["Austin, TX"],
                "badges": [],
                "completed_jobs": 28,
                "reviews_summary": "Good workmanship; occasional schedule slips.",
            },
            {
                "id": "c3",
                "name": "RapidFix Contractors",
                "trades": ["roof repair", "general repair"],
                "service_area": ["Austin, TX", "San Marcos, TX"],
                "badges": ["Verified Insurance"],
                "completed_jobs": 60,
                "reviews_summary": "Fast turnaround; ensure scope is documented.",
            },
        ]

    def create_project_draft(self, *, project_type: str, location: str, owner_key: str) -> str:
        """
        Create a project draft and store it.
        owner_key: for now we’ll use session_id as an owner placeholder.
        """
        project_id = new_id("proj_")
        self.projects[project_id] = {
            "id": project_id,
            "owner_key": owner_key,
            "project_type": project_type,
            "location": location,
            "status": "draft",
        }
        return project_id


# Singleton store instance used by all tools (good enough for Phase 2)
STORE = InMemoryStore()
STORE.seed_contractors()