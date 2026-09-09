"""One entry point every surface calls."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from . import store
from .audit import Audit
from .graph import run_graph
from .models import Brief, BriefItem
from .sources.github import GitHubError, GitHubSource
from .sources.local import LocalSource
from .target import is_path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _honest(target: str, reason: str, audit: Audit) -> Brief:
    return Brief(target=target, standing="Nothing to triage yet, and that is a fine place to be.",
                 items=[BriefItem(title="Point Standup at something it can read", evidence=reason,
                                  action="Try a public GitHub handle, or a folder that contains git repositories.",
                                  minutes=1, kind="thread", waiting_on=None, repo="-")],
                 beyond_tonight="Come back when there is a project to come back to.",
                 could_not_see=[reason], looked_at=list(audit.entries), generated_at=_now())


def run_standup(target: str, on_progress: Callable[[str], None] = lambda _: None) -> Brief:
    target = target.strip()
    audit = Audit(target)
    on_progress("looking")
    path = is_path(target)
    try:
        if path:
            states = LocalSource(target).read()
            audit.note(f"read {len(states)} local repositories with git and gh", target)
        else:
            states = GitHubSource(target).read()
            audit.note(f"read {len(states)} public repositories on GitHub", target)
    except GitHubError as exc:
        return _honest(target, str(exc), audit)
    if not states:
        reason = (f"no git repositories found in {target} or its subfolders" if path
                  else f"no repositories pushed in the last year for {target}")
        return _honest(target, reason, audit)
    previous = store.load(target)
    brief, _failed = run_graph(states, previous, audit, on_progress)
    store.save(brief)
    return brief
