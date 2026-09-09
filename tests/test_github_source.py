import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from standup.sources import github
from standup.sources.github import GitHubError, fetch_account, parse_account

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)
DATA = json.loads(Path("tests/fixtures/account.json").read_text())["data"]


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_parses_repos_newest_push_first():
    states = parse_account(DATA, NOW)
    assert states, "fixture has repos"
    days = [s.days_since_push for s in states]
    assert days == sorted(days)


def test_caps_at_twelve_and_drops_year_old_pushes():
    states = parse_account(DATA, NOW)
    assert len(states) <= 12
    assert all(s.days_since_push <= 365 for s in states)


def test_bot_authors_are_flagged():
    states = parse_account(DATA, NOW)
    bots = [t for s in states for t in s.open_prs if t.author.bot]
    humans = [t for s in states for t in s.open_prs if not t.author.bot]
    assert bots, "fixture contains dependabot PRs"
    assert all(t.author.login != "dependabot" for t in humans)


def test_threads_are_deduplicated_between_old_and_new_windows():
    states = parse_account(DATA, NOW)
    for s in states:
        numbers = [t.number for t in s.open_prs]
        assert len(numbers) == len(set(numbers))


def test_stale_branches_exclude_default_and_fresh():
    states = parse_account(DATA, NOW)
    for s in states:
        for b in s.stale_branches:
            assert b.name != s.default_branch
            assert b.days > 30


def test_rate_limited_response_names_rate_limit(monkeypatch):
    payload = {"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}
    monkeypatch.setattr(github.httpx, "post", lambda *a, **k: _FakeResponse(200, payload))
    with pytest.raises(GitHubError, match="(?i)rate limit"):
        fetch_account("someone", "token")


def test_unknown_login_names_the_login(monkeypatch):
    payload = {"errors": [{"type": "NOT_FOUND", "message": "Could not resolve to a User"}]}
    monkeypatch.setattr(github.httpx, "post", lambda *a, **k: _FakeResponse(200, payload))
    with pytest.raises(GitHubError, match="someone"):
        fetch_account("someone", "token")


def test_401_raises_github_error(monkeypatch):
    monkeypatch.setattr(github.httpx, "post", lambda *a, **k: _FakeResponse(401, {}))
    with pytest.raises(GitHubError):
        fetch_account("someone", "bad-token")


def test_partial_errors_with_owner_present_returns_data(monkeypatch):
    payload = {
        "errors": [{"type": "SOME_WARNING", "message": "a field warning"}],
        "data": {"repositoryOwner": {"login": "someone", "repositories": {"nodes": []}}},
    }
    monkeypatch.setattr(github.httpx, "post", lambda *a, **k: _FakeResponse(200, payload))
    data = fetch_account("someone", "token")
    assert data["repositoryOwner"]["login"] == "someone"
