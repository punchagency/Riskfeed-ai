from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)

def test_risk_check_uses_session_project_and_returns_risk_report():
    session_id = "s_risk_1"

    # Step 1: create project draft
    r1 = client.post("/chat", json={
        "role": "homeowner",
        "message": "Kitchen remodel in Austin budget 25000",
        "session_id": session_id,
        "confirm_action_id": None,
        "debug": True
    })
    assert r1.status_code == 200

    # Step 2: ask for risk (should reuse current_project_id from session memory)
    r2 = client.post("/chat", json={
        "role": "homeowner",
        "message": "What are the risks?",
        "session_id": session_id,
        "confirm_action_id": None,
        "debug": True
    })
    assert r2.status_code == 200
    data = r2.json()

    assert "Risk Score" in data["message"]
    assert data["debug"]["intent"] == "risk_check"
    assert isinstance(data["citations"], list)  # may be empty depending on retrieval match