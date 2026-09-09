"""One scout per repository in parallel, one triage. The ordering rule is enforced after the model."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from strands import Agent
from strands.multiagent import GraphBuilder

from .audit import Audit
from .models import Brief, BriefItem, RepoRead, RepoState
from .prompts import SCOUT_SYSTEM, TRIAGE_SYSTEM

ORDER = {"waiting": 0, "will_hurt": 1, "thread": 2}


def rank(items: list[BriefItem]) -> list[BriefItem]:
    return sorted(items, key=lambda i: ORDER[i.kind])


def node_id(repo: str) -> str:
    return "scout_" + re.sub(r"[^a-zA-Z0-9]", "_", repo)


def scout_agent(state: RepoState, model) -> Agent:
    kwargs = dict(system_prompt=SCOUT_SYSTEM.format(state=state.model_dump_json()),
                  structured_output_model=RepoRead, callback_handler=None)
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)


def triage_agent(model) -> Agent:
    kwargs = dict(system_prompt=TRIAGE_SYSTEM, structured_output_model=Brief, callback_handler=None)
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)


def build_graph(states: list[RepoState], model, audit: Audit):
    b = GraphBuilder()
    ids = []
    for s in states:
        nid = node_id(s.name)
        b.add_node(scout_agent(s, model), nid)
        b.set_entry_point(nid)
        ids.append(nid)
    b.add_node(triage_agent(model), "triage")
    for nid in ids:
        b.add_edge(nid, "triage")
    b.set_execution_timeout(120)
    b.set_hook_providers([audit])
    return b.build(), ids


def run_graph(states: list[RepoState], previous: Brief | None, audit: Audit,
              on_progress: Callable[[str], None] = lambda _: None) -> tuple[Brief, list[str]]:
    from .model import resolve
    model = resolve()
    graph, ids = build_graph(states, model, audit)
    task = "Scouts: read your project and report. Triage: produce the brief for the owner."
    if previous is not None:
        task += f"\n\nPrevious brief ({previous.generated_at}):\n{previous.model_dump_json()}"
    on_progress(f"reading {len(states)} projects")
    result = graph(task)
    failed = [s.name for s, nid in zip(states, ids)
              if nid not in result.results or result.results[nid].status.name != "COMPLETED"]
    node = result.results.get("triage")
    brief = getattr(getattr(node, "result", None), "structured_output", None)
    if not isinstance(brief, Brief):
        raise RuntimeError("triage did not return a brief")
    brief.items = rank(brief.items)
    brief.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    brief.could_not_see = list(brief.could_not_see) + [f"{n}: the scout could not read it" for n in failed]
    brief.looked_at = list(audit.entries)
    return brief, failed
