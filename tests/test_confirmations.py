from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)

# Test that an invite requires confirmation then executes
def test_invite_requires_confirmation_then_executes():
    # Step 1: create project draft (homeowner)
    r1 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Kitchen remodel in Austin budget 25000",
            "session_id": "s_confirm",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert r1.status_code == 200
    proj_line = [ln for ln in r1.json()["message"].splitlines() if "proj_" in ln]
    assert proj_line, "Expected project id to be created"
    project_id = proj_line[0].split(":")[-1].strip()

    # Step 2: invite contractor -> should return pending confirmation action
    r2 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": f"Invite c1 to {project_id}",
            "session_id": "s_confirm",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["actions"], "Expected an action requiring confirmation"
    action = data2["actions"][0]
    assert action["requires_confirmation"] is True
    confirm_id = action["confirm_action_id"]

    # Step 3: confirm -> should execute invite
    r3 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Confirm",
            "session_id": "s_confirm",
            "confirm_action_id": confirm_id,
            "debug": True,
        },
    )
    assert r3.status_code == 200
    assert "Invite sent" in r3.json()["message"]

    # Step 4: reuse same confirm_id -> should fail (single-use)
    r4 = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Confirm again",
            "session_id": "s_confirm",
            "confirm_action_id": confirm_id,
            "debug": True,
        },
    )
    assert r4.status_code == 200
    assert "already used" in r4.json()["message"].lower()