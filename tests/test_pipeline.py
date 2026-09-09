from standup.models import Brief, BriefItem, RepoState
from standup.pipeline import run_standup
from standup.sources.github import GitHubError


class _FakeErrorSource:
    def __init__(self, target: str):
        self.target = target

    def read(self):
        raise GitHubError("no public GitHub account called nobody")


class _FakeEmptySource:
    def __init__(self, target: str):
        self.target = target

    def read(self):
        return []


class _FakeEmptyLocalSource:
    def __init__(self, path: str):
        self.path = path

    def read(self):
        return []


def test_github_error_becomes_honest_brief(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr("standup.pipeline.GitHubSource", _FakeErrorSource)
    brief = run_standup("nobody")
    assert len(brief.items) == 1
    assert brief.could_not_see == ["no public GitHub account called nobody"]
    assert brief.looked_at == []


def test_empty_read_becomes_honest_brief(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr("standup.pipeline.GitHubSource", _FakeEmptySource)
    brief = run_standup("nobody")
    assert len(brief.items) == 1
    assert "no repositories pushed in the last year" in brief.could_not_see[0]


def test_empty_local_read_says_no_git_repositories(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr("standup.pipeline.LocalSource", _FakeEmptyLocalSource)
    brief = run_standup(str(tmp_path))
    assert "no git repositories found" in brief.could_not_see[0]


class _FakeOneRepoSource:
    read_by = []

    def __init__(self, target: str):
        self.target = target

    def read(self):
        _FakeOneRepoSource.read_by.append(self.target)
        return [RepoState(name="r", url="u", owner="someone", days_since_push=1, default_branch="main")]


def _brief(target):
    return Brief(target=target, standing="s", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="t", evidence="e", action="a", minutes=5, kind="thread",
                                  waiting_on=None, repo="r")])


def test_the_saved_brief_is_keyed_on_the_requested_target(monkeypatch, tmp_path):
    """The model fills Brief.target; the request decides where the session file lands."""
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr("standup.pipeline.GitHubSource", _FakeOneRepoSource)
    monkeypatch.setattr("standup.pipeline.run_graph",
                        lambda states, previous, audit, on_progress: (_brief("wrong-name"), []))
    brief = run_standup("yannvr")
    assert brief.target == "yannvr"
    assert (tmp_path / "yannvr.json").exists() and not (tmp_path / "wrong-name.json").exists()


def test_the_page_can_pin_the_source_to_github(monkeypatch, tmp_path):
    """"src" exists on disk here; a visitor must not be able to read the server's filesystem."""
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    _FakeOneRepoSource.read_by = []
    monkeypatch.setattr("standup.pipeline.GitHubSource", _FakeOneRepoSource)
    monkeypatch.setattr("standup.pipeline.LocalSource", _FakeEmptyLocalSource)
    monkeypatch.setattr("standup.pipeline.run_graph",
                        lambda states, previous, audit, on_progress: (_brief("src"), []))
    brief = run_standup("src", source="github")
    assert _FakeOneRepoSource.read_by == ["src"] and brief.target == "src"


def test_progress_names_each_scout_as_it_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr("standup.pipeline.GitHubSource", _FakeOneRepoSource)

    def _graph(states, previous, audit, on_progress):
        audit.node("scout_0_r")
        return _brief("x"), []

    monkeypatch.setattr("standup.pipeline.run_graph", _graph)
    lines = []
    run_standup("yannvr", on_progress=lines.append)
    assert "scout 1 of 1" in lines
    assert any(line.startswith("read 1 public repositories") for line in lines)
