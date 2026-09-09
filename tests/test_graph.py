import pytest

from standup.audit import Audit
from standup.graph import node_id, rank, run_graph
from standup.models import Brief, BriefItem, RepoRead, RepoState


def it(kind, waiting_on=None, title="x"):
    return BriefItem(title=title, evidence="e", action="a", minutes=5, kind=kind, waiting_on=waiting_on, repo="r")


def test_waiting_outranks_private_which_outranks_thread():
    items = [it("thread", title="t"), it("will_hurt", title="h"), it("waiting", "alice", title="w")]
    assert [i.title for i in rank(items)] == ["w", "h", "t"]


def test_rank_is_stable_within_a_kind():
    items = [it("thread", title="a"), it("thread", title="b")]
    assert [i.title for i in rank(items)] == ["a", "b"]


def test_node_ids_are_safe():
    assert node_id("my.repo-name") == "scout_my_repo_name"


def _state(name: str) -> RepoState:
    return RepoState(name=name, url=f"https://example.test/{name}", days_since_push=1, default_branch="main")


class _FakeResult:
    def __init__(self, structured_output):
        self.structured_output = structured_output


class _FakeAgent:
    def __init__(self, structured_output=None, raises: bool = False):
        self._out = structured_output
        self._raises = raises

    async def invoke_async(self, *args, **kwargs):
        if self._raises:
            raise RuntimeError("scout exploded")
        return _FakeResult(self._out)


def _boom_graph(task):
    raise RuntimeError("boom")


def _patch_no_graph(monkeypatch):
    monkeypatch.setattr(
        "standup.graph.build_graph",
        lambda states, model, audit: (_boom_graph, [node_id(s.name) for s in states]),
    )
    monkeypatch.setattr("standup.model.resolve", lambda: None)


def test_a_failed_scout_is_dropped_and_named_when_the_graph_fails(monkeypatch):
    states = [_state("a"), _state("b"), _state("c")]
    _patch_no_graph(monkeypatch)

    def fake_scout_agent(state, model):
        if state.name == "b":
            return _FakeAgent(raises=True)
        return _FakeAgent(structured_output=RepoRead(repo=state.name, moved="nothing"))

    monkeypatch.setattr("standup.graph.scout_agent", fake_scout_agent)

    unranked = Brief(
        target="t", standing="s",
        items=[it("thread", title="t1"), it("waiting", "alice", title="w1")],
        beyond_tonight="b", generated_at="placeholder",
    )
    monkeypatch.setattr("standup.graph.triage_agent", lambda model: _FakeAgent(structured_output=unranked))

    audit = Audit("acct")
    brief, failed = run_graph(states, None, audit)

    assert failed == ["b"]
    assert any("b" in line for line in brief.could_not_see)
    scout_notes = [e for e in audit.entries if e.what.startswith("ran scout_")]
    assert len(scout_notes) == len(states)
    assert [i.kind for i in brief.items] == ["waiting", "thread"]


def test_a_failed_triage_is_one_plain_line_when_the_graph_fails(monkeypatch):
    states = [_state("a")]
    _patch_no_graph(monkeypatch)
    monkeypatch.setattr(
        "standup.graph.scout_agent",
        lambda state, model: _FakeAgent(structured_output=RepoRead(repo=state.name, moved="x")),
    )
    monkeypatch.setattr("standup.graph.triage_agent", lambda model: _FakeAgent(raises=True))

    audit = Audit("acct")
    with pytest.raises(RuntimeError, match="^Standup could not finish the brief"):
        run_graph(states, None, audit)
