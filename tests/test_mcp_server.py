from standup.models import Brief, BriefItem
from standup import mcp_server


def _brief(target="x"):
    return Brief(target=target, standing="s", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="t", evidence="e", action="a", minutes=5, kind="thread", waiting_on=None, repo="r")])


def test_tool_returns_dict_with_text_and_items(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr(mcp_server, "run_standup", lambda target: _brief(target))
    out = mcp_server.standup("x")
    assert isinstance(out, dict)
    assert "text" in out and "s" in out["text"]
    assert "items" in out and out["items"][0]["title"] == "t"
