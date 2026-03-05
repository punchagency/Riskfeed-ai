from riskfeed.tools.project import create_project_draft
from riskfeed.tools.contractor import list_contractors


def test_create_project_draft_tool():
    out = create_project_draft(
        {"project_type": "kitchen remodel", "location": "Austin, TX", "owner_key": "s1"}
    )
    assert out["ok"] is True
    assert out["tool_name"] == "project.create_project_draft"
    assert "project_id" in out["data"]


def test_list_contractors_tool():
    out = list_contractors({})
    assert out["ok"] is True
    assert out["tool_name"] == "contractor.list_contractors"
    assert isinstance(out["data"]["contractors"], list)
    assert len(out["data"]["contractors"]) >= 1