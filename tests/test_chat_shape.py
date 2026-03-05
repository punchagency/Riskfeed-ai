from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)

def test_chat_shape():
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "I want to remodel my kitchen",
            "session_id": "test_session",
            "confirm_action_id": None,
            "debug": False,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # Key contract fields
    for key in ["message", "role", "checklist", "missing_info", "actions", "citations", "debug"]:
        assert key in data
    assert data["role"] == "homeowner"
    assert isinstance(data["checklist"], list)
    assert isinstance(data["missing_info"], list)
    assert isinstance(data["actions"], list)
    assert isinstance(data["citations"], list)
    assert isinstance(data["debug"], dict)
    