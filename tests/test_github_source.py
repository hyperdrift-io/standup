import json
from datetime import datetime, timezone
from pathlib import Path

from standup.sources.github import parse_account

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)
DATA = json.loads(Path("tests/fixtures/account.json").read_text())["data"]


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
