"""Typed shapes shared by every source, agent and surface. No behaviour beyond validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Author(BaseModel):
    login: str
    bot: bool = False


class Thread(BaseModel):
    number: int
    title: str
    url: str
    days: int
    author: Author
    kind: Literal["pr", "issue"]
    review: str | None = None
    draft: bool = False
    comments: int = 0


class Branch(BaseModel):
    name: str
    days: int


class RepoState(BaseModel):
    name: str
    url: str
    owner: str = ""
    days_since_push: int
    default_branch: str
    ci: str | None = None
    recent_commits: list[str] = []
    open_prs: list[Thread] = []
    open_issues: list[Thread] = []
    stale_branches: list[Branch] = []
    uncommitted: int | None = None
    unpushed: int | None = None
    behind: int | None = None


class Waiting(BaseModel):
    who: str
    what: str
    days: int
    url: str


class RepoRead(BaseModel):
    repo: str
    moved: str
    waiting: list[Waiting] = []
    will_hurt: list[str] = []
    dropped_thread: str | None = None


class BriefItem(BaseModel):
    title: str
    evidence: str
    action: str
    minutes: int = Field(gt=0)
    kind: Literal["waiting", "will_hurt", "thread"]
    waiting_on: str | None = None
    repo: str

    @model_validator(mode="after")
    def waiting_names_someone(self) -> "BriefItem":
        if self.waiting_on:
            self.kind = "waiting"  # naming a person is what makes an item a waiting item
        elif self.kind == "waiting":
            raise ValueError("a waiting item must name who is waiting")
        return self


class LookedAt(BaseModel):
    when: str
    what: str
    target: str


class Brief(BaseModel):
    target: str
    standing: str
    items: list[BriefItem] = Field(min_length=1, max_length=3)
    beyond_tonight: str
    could_not_see: list[str] = []
    looked_at: list[LookedAt] = []
    generated_at: str
