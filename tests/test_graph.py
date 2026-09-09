import pytest

from standup.audit import Audit
from standup.graph import build_graph, node_id, rank, run_graph
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
    assert node_id("my.repo-name", 3) == "scout_3_my_repo_name"


def test_repos_that_sanitise_to_the_same_id_still_build_a_graph():
    graph, ids = build_graph([_state("my-app"), _state("my_app")], None, Audit("acct"))
    assert len(set(ids)) == 2 and graph is not None


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
        lambda states, model, audit: (_boom_graph, [node_id(s.name, n) for n, s in enumerate(states)]),
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
    triage_notes = [e for e in brief.looked_at if e.what == "ran triage"]
    assert len(triage_notes) == 1
    assert [i.kind for i in brief.items] == ["waiting", "thread"]
    fallback_notes = [e for e in audit.entries if "reading projects individually" in e.what]
    assert len(fallback_notes) == 1
    assert fallback_notes[0].what == "first pass stopped early; reading projects individually"
    assert "RuntimeError" not in fallback_notes[0].what
    assert fallback_notes[0].target == "RuntimeError"


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


def test_a_broken_model_configuration_fails_loudly_instead_of_falling_back(monkeypatch):
    states = [_state("a")]

    def _boom():
        raise ValueError("no credentials")

    monkeypatch.setattr("standup.model.resolve", _boom)

    with pytest.raises(RuntimeError, match=r"^Standup could not finish the brief \(model configuration\)$"):
        run_graph(states, None, Audit("acct"))


def test_an_item_that_names_someone_ranks_first_whatever_its_kind():
    items = [it("will_hurt", title="h"), it("thread", waiting_on="alice", title="w")]
    assert [i.title for i in rank(items)] == ["w", "h"]
    assert items[1].kind == "waiting"


def test_the_owner_is_never_someone_waiting_on_themselves(monkeypatch):
    states = [_state("a")]
    _patch_no_graph(monkeypatch)
    monkeypatch.setattr(
        "standup.graph.scout_agent",
        lambda state, model: _FakeAgent(structured_output=RepoRead(repo=state.name, moved="x")),
    )
    self_waiting = Brief(target="yannvr", standing="s", beyond_tonight="b", generated_at="p",
                         items=[it("waiting", "YannVR", title="self")])
    monkeypatch.setattr("standup.graph.triage_agent", lambda model: _FakeAgent(structured_output=self_waiting))
    brief, _ = run_graph(states, None, Audit("yannvr"))
    assert brief.items[0].waiting_on is None and brief.items[0].kind == "thread"
