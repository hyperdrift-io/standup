import asyncio

from standup.models import Brief, BriefItem
from standup import mcp_server


def _brief(target="x"):
    return Brief(target=target, standing="s", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="t", evidence="e", action="a", minutes=5, kind="thread", waiting_on=None, repo="r")])


def test_tool_returns_dict_with_text_and_items(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr(mcp_server, "run_standup", lambda target: _brief(target))
    out = asyncio.run(mcp_server.standup("x"))
    assert isinstance(out, dict)
    assert "text" in out and "s" in out["text"]
    assert "items" in out and out["items"][0]["title"] == "t"


def test_tool_survives_a_run_that_starts_its_own_event_loop(monkeypatch, tmp_path):
    """MCP hosts call the tool from a running loop; the run's own asyncio.run must not collide."""
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))

    async def _trivial():
        return None

    def _blocking_run(target):
        asyncio.run(_trivial())
        return _brief(target)

    monkeypatch.setattr(mcp_server, "run_standup", _blocking_run)

    async def _host():
        return await mcp_server.standup("x")

    out = asyncio.run(_host())
    assert out["items"][0]["title"] == "t"
