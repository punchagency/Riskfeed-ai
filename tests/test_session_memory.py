from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)


def test_session_memory_reuses_location_budget_and_project():
    session_id = "s_mem_1"

    # Step 1: Provide full info and create draft
    r1 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Kitchen remodel in Austin budget 25000",
            "session_id": session_id,
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert r1.status_code == 200
    msg1 = r1.json()["message"]
    assert "Project draft created" in msg1 or "proj_" in msg1

    # Extract project id
    project_id = None
    for ln in msg1.splitlines():
        if "proj_" in ln:
            project_id = ln.split(":")[-1].strip()
    assert project_id is not None

    # Step 2: Ask to find contractors WITHOUT repeating location/budget
    r2 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Find contractor",
            "session_id": session_id,
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()

    # Should NOT ask missing info again (memory should fill it)
    assert data2["missing_info"] == []

    # Should show contractor list
    assert "Lone Star Kitchens" in data2["message"]

    # Should reuse existing project draft
    assert project_id in data2["message"]