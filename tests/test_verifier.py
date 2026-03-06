from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)


def test_verifier_passes_normal_flow():
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Do I need permits for a kitchen remodel?",
            "session_id": "s_verify",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Should not hit repair fallback
    assert "consistency check" not in data["message"].lower()


def test_repair_triggers_when_message_empty():
    # We'll trigger by sending an empty message (should fail verifier rule 1)
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "   ",
            "session_id": "s_verify2",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    assert "consistency check" in res.json()["message"].lower()