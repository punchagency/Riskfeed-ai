# tests/test_hardening.py
from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)


def test_debug_includes_trace_id():
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Do I need permits for a kitchen remodel?",
            "session_id": "s_trace_1",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert "debug" in data
    assert "trace_id" in data["debug"]
    assert isinstance(data["debug"]["trace_id"], str)
    assert data["debug"]["trace_id"].startswith("trace_")


def test_tool_exception_does_not_crash_api():
    """
    This requires the debug.crash_tool to exist and planner to call it
    when message includes 'crash tool'.
    """
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "crash tool",
            "session_id": "s_crash_1",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # Response shape must still be valid
    assert "message" in data
    assert "citations" in data
    assert "actions" in data

    # Debug should show a tool call happened
    assert "tool_calls" in data["debug"]
    assert len(data["debug"]["tool_calls"]) >= 1

    
    assert ("tool" in data["message"].lower()) or ("error" in data["message"].lower()) or ("exception" in data["message"].lower())