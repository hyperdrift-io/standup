from standup.graph import rank, node_id
from standup.models import BriefItem


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
