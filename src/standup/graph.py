"""One scout per repository in parallel, one triage. The ordering rule is enforced after the model.

strands 1.55's Graph is fail-fast: a scout's model error is re-raised and cancels its siblings,
so `graph(task)` can raise instead of leaving the failure in `result.results`. When that happens we
fall back to reading each scout one at a time with `asyncio.gather(return_exceptions=True)`-style
isolation, so a failed scout is dropped and named (spec 3.6) instead of losing the whole run, and a
failed triage surfaces as one plain line, never a raw stack trace.
"""
from __future__ import annotations

import asyncio
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


def _finish(brief: Brief, failed: list[str], audit: Audit) -> Brief:
    brief.items = rank(brief.items)
    brief.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    brief.could_not_see = list(brief.could_not_see) + [f"{n}: the scout could not read it" for n in failed]
    brief.looked_at = list(audit.entries)
    return brief


async def _scout_async(state: RepoState, model, audit: Audit) -> RepoRead | None:
    audit.note(f"ran {node_id(state.name)}")
    try:
        result = await scout_agent(state, model).invoke_async("Read your project and report.")
        read = result.structured_output
    except Exception:
        return None
    return read if isinstance(read, RepoRead) else None


async def _gather(states: list[RepoState], previous: Brief | None, model, audit: Audit,
                   on_progress: Callable[[str], None]) -> tuple[Brief, list[str]]:
    on_progress(f"reading {len(states)} projects one by one")
    reads = await asyncio.gather(*[_scout_async(s, model, audit) for s in states])
    failed = [s.name for s, r in zip(states, reads) if r is None]
    prompt = "Triage: produce the brief for the owner.\n\nScout reports (JSON):\n" + \
        "\n".join(r.model_dump_json() for r in reads if r is not None)
    if previous is not None:
        prompt += f"\n\nPrevious brief ({previous.generated_at}):\n{previous.model_dump_json()}"
    try:
        result = await triage_agent(model).invoke_async(prompt)
        brief = result.structured_output
    except Exception as exc:
        raise RuntimeError(f"Standup could not finish the brief ({exc.__class__.__name__})") from exc
    if not isinstance(brief, Brief):
        raise RuntimeError("Standup could not finish the brief (no structured output)")
    return _finish(brief, failed, audit), failed


def run_graph(states: list[RepoState], previous: Brief | None, audit: Audit,
              on_progress: Callable[[str], None] = lambda _: None) -> tuple[Brief, list[str]]:
    from .model import resolve
    model = resolve()
    graph, ids = build_graph(states, model, audit)
    task = "Scouts: read your project and report. Triage: produce the brief for the owner."
    if previous is not None:
        task += f"\n\nPrevious brief ({previous.generated_at}):\n{previous.model_dump_json()}"
    on_progress(f"reading {len(states)} projects")
    try:
        result = graph(task)
    except Exception as exc:
        audit.note(f"graph stopped early: {exc.__class__.__name__}; reading projects one by one")
        return asyncio.run(_gather(states, previous, model, audit, on_progress))
    failed = [s.name for s, nid in zip(states, ids)
              if nid not in result.results or result.results[nid].status.name != "COMPLETED"]
    node = result.results.get("triage")
    brief = getattr(getattr(node, "result", None), "structured_output", None)
    if not isinstance(brief, Brief):
        raise RuntimeError("Standup could not finish the brief (no structured output)")
    return _finish(brief, failed, audit), failed
