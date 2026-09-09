"""Read an account's public repositories in one GraphQL call. Read-only by construction."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

import httpx

from ..models import Author, Branch, RepoState, Thread

API = "https://api.github.com/graphql"
MAX_REPOS = 12
ACTIVE_DAYS = 365
STALE_DAYS = 30

QUERY = """
query($login:String!){ rateLimit{cost remaining}
 repositoryOwner(login:$login){ login
  repositories(first:20, ownerAffiliations:OWNER, isFork:false, isArchived:false, orderBy:{field:PUSHED_AT,direction:DESC}){ totalCount
   nodes{ name url pushedAt
    defaultBranchRef{ name target{ ... on Commit{ statusCheckRollup{state} history(first:8){nodes{messageHeadline committedDate}} } } }
    oldPRs: pullRequests(states:OPEN,first:5,orderBy:{field:UPDATED_AT,direction:ASC}){ totalCount nodes{number title url updatedAt isDraft reviewDecision author{login __typename}} }
    newPRs: pullRequests(states:OPEN,first:5,orderBy:{field:UPDATED_AT,direction:DESC}){ nodes{number title url updatedAt isDraft reviewDecision author{login __typename}} }
    oldIssues: issues(states:OPEN,first:5,orderBy:{field:UPDATED_AT,direction:ASC}){ totalCount nodes{number title url updatedAt author{login __typename} comments{totalCount}} }
    newIssues: issues(states:OPEN,first:5,orderBy:{field:UPDATED_AT,direction:DESC}){ nodes{number title url updatedAt author{login __typename} comments{totalCount}} }
    refs(refPrefix:"refs/heads/",first:30){ totalCount nodes{name target{... on Commit{committedDate}}} }
 }}}}
"""


class GitHubError(RuntimeError):
    """A read failed in a way the brief should name, never hide."""


def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def fetch_account(login: str, token: str) -> dict:
    if not token:
        raise GitHubError("no GitHub token: set GITHUB_TOKEN or sign in with gh")
    try:
        r = httpx.post(API, json={"query": QUERY, "variables": {"login": login}},
                       headers={"Authorization": f"bearer {token}"}, timeout=20)
    except httpx.HTTPError as exc:
        raise GitHubError(f"GitHub did not answer: {exc.__class__.__name__}") from exc
    if r.status_code == 401:
        raise GitHubError("GitHub rejected the token")
    if r.status_code != 200:
        raise GitHubError(f"GitHub answered {r.status_code}")
    body = r.json()
    errors = body.get("errors") or []
    if errors and not (body.get("data") or {}).get("repositoryOwner"):
        if any(
            e.get("type") == "RATE_LIMITED" or "rate limit" in str(e.get("message", "")).lower()
            for e in errors
        ):
            raise GitHubError("GitHub rate limit reached for this token; try again in an hour")
        raise GitHubError(f"no public GitHub account called {login}")
    if "data" not in body:
        raise GitHubError("GitHub answered without data")
    return body["data"]


def _days(iso: str | None, now: datetime) -> int:
    if not iso:
        return 0
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (now - then).days)


def _author(node: dict | None) -> Author:
    if not node:
        return Author(login="ghost", bot=False)
    return Author(login=node.get("login", "ghost"), bot=node.get("__typename") == "Bot")


def _threads(old: list, new: list, kind: str, now: datetime) -> list[Thread]:
    seen: dict[int, Thread] = {}
    for n in old + new:
        if n["number"] in seen:
            continue
        seen[n["number"]] = Thread(
            number=n["number"], title=n["title"], url=n["url"], days=_days(n.get("updatedAt"), now),
            author=_author(n.get("author")), kind=kind,
            review=n.get("reviewDecision"), draft=bool(n.get("isDraft")),
            comments=(n.get("comments") or {}).get("totalCount", 0),
        )
    return sorted(seen.values(), key=lambda t: -t.days)


def parse_account(data: dict, now: datetime | None = None) -> list[RepoState]:
    now = now or datetime.now(timezone.utc)
    owner = data.get("repositoryOwner") or {}
    states: list[RepoState] = []
    for r in (owner.get("repositories") or {}).get("nodes", []):
        days = _days(r.get("pushedAt"), now)
        if days > ACTIVE_DAYS:
            continue
        ref = r.get("defaultBranchRef") or {}
        head = ref.get("target") or {}
        default = ref.get("name") or "main"
        stale = [
            Branch(name=b["name"], days=_days((b.get("target") or {}).get("committedDate"), now))
            for b in (r.get("refs") or {}).get("nodes", [])
            if b.get("name") != default and b.get("target")
        ]
        states.append(RepoState(
            name=r["name"], url=r["url"], days_since_push=days, default_branch=default,
            ci=(head.get("statusCheckRollup") or {}).get("state"),
            recent_commits=[c["messageHeadline"] for c in (head.get("history") or {}).get("nodes", [])],
            open_prs=_threads(r["oldPRs"]["nodes"], r["newPRs"]["nodes"], "pr", now),
            open_issues=_threads(r["oldIssues"]["nodes"], r["newIssues"]["nodes"], "issue", now),
            stale_branches=sorted([b for b in stale if b.days > STALE_DAYS], key=lambda b: -b.days)[:6],
        ))
    states.sort(key=lambda s: s.days_since_push)
    return states[:MAX_REPOS]


class GitHubSource:
    def __init__(self, handle: str):
        self.handle = handle.strip().lstrip("@")

    def read(self) -> list[RepoState]:
        return parse_account(fetch_account(self.handle, github_token()))
