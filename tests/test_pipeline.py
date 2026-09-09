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
