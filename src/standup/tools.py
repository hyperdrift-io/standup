"""Tools the agent uses to read a project's real state. No mocks, no writes."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from strands import tool

TIMEOUT = 20


def _run(args: list[str], cwd: str | Path) -> str:
    try:
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _days_since(iso: str) -> int | None:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).days
    except ValueError:
        return None


@tool
def list_projects(root: str) -> str:
    """List the git repositories under a directory, newest activity first.

    Use this when the person has not named a project, to see what they are juggling.

    Args:
        root: A directory that contains one or more git repositories.
    """
    base = Path(root).expanduser()
    if not base.is_dir():
        return f"No directory at {base}."
    repos = []
    for git_dir in base.glob("*/.git"):
        repo = git_dir.parent
        last = _run(["git", "log", "-1", "--format=%cI"], repo)
        repos.append({"path": str(repo), "name": repo.name, "days_since_commit": _days_since(last) if last else None})
    for git_dir in base.glob("*/*/.git"):
        repo = git_dir.parent
        last = _run(["git", "log", "-1", "--format=%cI"], repo)
        repos.append({"path": str(repo), "name": repo.name, "days_since_commit": _days_since(last) if last else None})
    repos.sort(key=lambda r: (r["days_since_commit"] is None, r["days_since_commit"]))
    return json.dumps(repos[:40], indent=1) if repos else f"No git repositories under {base}."


@tool
def project_snapshot(path: str) -> str:
    """Read where a project was left: branch, uncommitted work, unpushed commits, recent commits, stale branches.

    This is the core of a handover — what the person was in the middle of when they stopped.

    Args:
        path: Path to a git repository.
    """
    repo = Path(path).expanduser()
    if not (repo / ".git").exists():
        return f"{repo} is not a git repository."

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    dirty = [l for l in _run(["git", "status", "--porcelain"], repo).splitlines() if l]
    last_iso = _run(["git", "log", "-1", "--format=%cI"], repo)
    upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
    ahead = behind = None
    if upstream:
        counts = _run(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"], repo)
        if counts and "\t" in counts:
            behind, ahead = (int(x) for x in counts.split("\t"))

    branches = []
    for line in _run(["git", "for-each-ref", "--format=%(refname:short)|%(committerdate:iso-strict)", "refs/heads/"], repo).splitlines():
        if "|" not in line:
            continue
        name, when = line.split("|", 1)
        age = _days_since(when)
        if name != branch and age is not None and age > 7:
            branches.append({"branch": name, "days_stale": age})
    branches.sort(key=lambda b: -b["days_stale"])

    snapshot = {
        "path": str(repo),
        "branch": branch,
        "days_since_last_commit": _days_since(last_iso) if last_iso else None,
        "last_commit": _run(["git", "log", "-1", "--format=%s"], repo),
        "uncommitted_files": len(dirty),
        "uncommitted_sample": [d[3:] for d in dirty[:8]],
        "unpushed_commits": ahead,
        "behind_upstream": behind,
        "recent_commits": _run(["git", "log", "-8", "--format=%cs %s"], repo).splitlines(),
        "stale_branches": branches[:6],
    }
    return json.dumps(snapshot, indent=1)


@tool
def open_threads(path: str) -> str:
    """List the open pull requests and issues on a project's GitHub repo, oldest first.

    Use this to find work someone else is waiting on, which usually outranks anything local.

    Args:
        path: Path to a git repository with a GitHub remote.
    """
    repo = Path(path).expanduser()
    prs = _run(["gh", "pr", "list", "--limit", "10", "--json", "number,title,updatedAt,isDraft,reviewDecision"], repo)
    issues = _run(["gh", "issue", "list", "--limit", "10", "--json", "number,title,updatedAt,labels"], repo)
    if not prs and not issues:
        return "No GitHub remote, or the gh CLI is not authenticated for this repo."

    def age(items: str) -> list:
        out = []
        for it in json.loads(items or "[]"):
            it["days_since_update"] = _days_since(it.pop("updatedAt", "") or "")
            out.append(it)
        return sorted(out, key=lambda i: -(i["days_since_update"] or 0))

    return json.dumps({"open_prs": age(prs), "open_issues": age(issues)}, indent=1)


@tool
def ci_status(path: str) -> str:
    """Read the most recent CI runs for a project, so a red pipeline is not missed.

    Args:
        path: Path to a git repository with a GitHub remote.
    """
    repo = Path(path).expanduser()
    runs = _run(["gh", "run", "list", "--limit", "5", "--json", "conclusion,status,workflowName,createdAt,headBranch"], repo)
    if not runs:
        return "No CI runs visible for this repo."
    out = []
    for r in json.loads(runs):
        r["days_ago"] = _days_since(r.pop("createdAt", "") or "")
        out.append(r)
    return json.dumps(out, indent=1)
