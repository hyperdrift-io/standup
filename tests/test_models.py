import pytest
from pydantic import ValidationError
from standup.models import Brief, BriefItem


def item(**kw):
    base = dict(title="t", evidence="e", action="a", minutes=10, kind="thread", waiting_on=None, repo="r")
    base.update(kw)
    return BriefItem(**base)


def test_brief_accepts_one_to_three_items():
    for n in (1, 2, 3):
        Brief(target="x", standing="s", items=[item()] * n, beyond_tonight="b", generated_at="2026-09-09T00:00:00Z")


def test_brief_rejects_zero_and_four_items():
    for n in (0, 4):
        with pytest.raises(ValidationError):
            Brief(target="x", standing="s", items=[item()] * n, beyond_tonight="b", generated_at="now")


def test_minutes_must_be_positive():
    with pytest.raises(ValidationError):
        item(minutes=0)


def test_waiting_item_requires_waiting_on():
    with pytest.raises(ValidationError):
        item(kind="waiting", waiting_on=None)


def test_naming_someone_makes_an_item_a_waiting_item():
    assert item(kind="thread", waiting_on="alice").kind == "waiting"


def test_repo_state_carries_its_owner():
    from standup.models import RepoState
    assert RepoState(name="r", url="u", owner="yannvr", days_since_push=1, default_branch="main").owner == "yannvr"
