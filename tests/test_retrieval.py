from fastapi.testclient import TestClient
from riskfeed.api.main import app

client = TestClient(app)


def test_chat_returns_citations_for_permits_query():
    res = client.post(
        "/chat",
        json={
            "role": "homeowner",
            "message": "Do I need permits for a kitchen remodel?",
            "session_id": "s_rag",
            "confirm_action_id": None,
            "debug": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert isinstance(data["citations"], list)
    assert len(data["citations"]) >= 1

    # Should reference our permits.md doc
    uris = [c["uri"] for c in data["citations"]]
    assert any("permits.md" in u for u in uris)

    assert "retrieval" in data["debug"]
    assert data["debug"]["retrieval"]["hits"] >= 1

    assert "Here's what matters" in data["message"]