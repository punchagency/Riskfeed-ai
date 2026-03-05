from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)

# Test that a contractor cannot create a project draft
def test_contractor_cannot_create_project_draft():
    res = client.post(
        "/chat",
        json={
            "role": "contractor",
            "message": "I want to remodel my kitchen in Austin budget 25000",
            "session_id": "s_contractor",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # The tool should be denied
    assert "RBAC denied" in data["message"]