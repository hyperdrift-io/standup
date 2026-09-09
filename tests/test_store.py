import os
import time

from standup.models import Brief, BriefItem
from standup import store


def brief(target="yannvr"):
    return Brief(target=target, standing="s", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="t", evidence="e", action="a", minutes=5, kind="thread", waiting_on=None, repo="r")])


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    assert store.load("yannvr") is None
    store.save(brief())
    assert store.load("yannvr").standing == "s"


def test_handle_is_normalised_and_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    store.save(brief("../Evil"))
    assert (tmp_path / "evil.json").exists()


def test_sweep_removes_old_files(tmp_path, monkeypatch):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    p = store.save(brief())
    old = time.time() - 8 * 86400
    os.utime(p, (old, old))
    assert store.sweep(days=7) == 1
    assert store.load("yannvr") is None
