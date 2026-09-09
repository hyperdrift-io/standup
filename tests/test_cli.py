import json

from standup.models import Brief, BriefItem
from standup import cli


def _brief(target="x"):
    return Brief(target=target, standing="s", beyond_tonight="b", generated_at="2026-09-09T00:00:00Z",
                 items=[BriefItem(title="t", evidence="e", action="a", minutes=5, kind="thread", waiting_on=None, repo="r")])


def test_json_flag_prints_valid_json_with_target(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr(cli, "run_standup", lambda target, on_progress=None: _brief(target))
    cli.main(["x", "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["target"] == "x"


def test_default_prints_rendered_text(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("STANDUP_STATE", str(tmp_path))
    monkeypatch.setattr(cli, "run_standup", lambda target, on_progress=None: _brief(target))
    cli.main(["x"])
    out = capsys.readouterr().out
    assert "s" in out
    assert "1. t" in out
