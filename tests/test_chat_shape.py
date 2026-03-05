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
    
def test_chat_match_contractors_uses_tools_and_returns_contractors():
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Find contractor for kitchen remodel in Austin budget 25000",
            "session_id": "s_tools",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # should include contractor names in the message
    assert "Lone Star Kitchens" in data["message"]

    # debug should show tool calls since debug=True
    assert "tool_calls" in data["debug"]
    assert len(data["debug"]["tool_calls"]) >= 1