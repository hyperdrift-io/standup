"""Read local repositories with git and the gh CLI. Looks, never changes."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models import Author, Branch, RepoState, Thread

TIMEOUT = 20


def _run(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _days(iso: str, now: datetime) -> int:
    try:
        return max(0, (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days)
    except ValueError:
        return 0


def _threads(raw: str, kind: str, now: datetime) -> list[Thread]:
    out = []
    for it in json.loads(raw or "[]"):
        out.append(Thread(
            number=it["number"], title=it["title"], url=it.get("url", ""), days=_days(it.get("updatedAt", ""), now),
            author=Author(login=(it.get("author") or {}).get("login", "ghost"), bot=(it.get("author") or {}).get("is_bot", False)),
            kind=kind, review=it.get("reviewDecision"), draft=bool(it.get("isDraft")),
            comments=len(it.get("comments") or []),
        ))
    return sorted(out, key=lambda t: -t.days)


def read_repo(repo: Path, now: datetime | None = None) -> RepoState:
    now = now or datetime.now(timezone.utc)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo) or "main"
    dirty = [l for l in _run(["git", "status", "--porcelain"], repo).splitlines() if l]
    last_iso = _run(["git", "log", "-1", "--format=%cI"], repo)
    upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    ahead = behind = None
    if upstream:
        counts = _run(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"], repo)
        if "\t" in counts:
            behind, ahead = (int(x) for x in counts.split("\t"))
    stale = []
    for line in _run(["git", "for-each-ref", "--format=%(refname:short)|%(committerdate:iso-strict)", "refs/heads/"], repo).splitlines():
        if "|" not in line:
            continue
        name, when = line.split("|", 1)
        age = _days(when, now)
        if name != branch and age > 7:
            stale.append(Branch(name=name, days=age))
    url = _run(["gh", "repo", "view", "--json", "url", "-q", ".url"], repo)
    prs = _run(["gh", "pr", "list", "--limit", "10", "--json", "number,title,url,updatedAt,isDraft,reviewDecision,author"], repo)
    issues = _run(["gh", "issue", "list", "--limit", "10", "--json", "number,title,url,updatedAt,author,comments"], repo)
    runs = _run(["gh", "run", "list", "--limit", "1", "--json", "conclusion", "-q", ".[0].conclusion"], repo)
    return RepoState(
        name=repo.name, url=url or str(repo), days_since_push=_days(last_iso, now) if last_iso else 0,
        default_branch=branch, ci=(runs.upper() or None) if runs else None,
        recent_commits=_run(["git", "log", "-8", "--format=%s"], repo).splitlines(),
        open_prs=_threads(prs, "pr", now), open_issues=_threads(issues, "issue", now),
        stale_branches=sorted(stale, key=lambda b: -b.days)[:6],
        uncommitted=len(dirty), unpushed=ahead, behind=behind,
    )


class LocalSource:
    def __init__(self, path: str):
        self.root = Path(path).expanduser()

    def read(self) -> list[RepoState]:
        if (self.root / ".git").exists():
            return [read_repo(self.root)]
        repos = sorted(p.parent for p in self.root.glob("*/.git"))
        return [read_repo(r) for r in repos[:12]]
