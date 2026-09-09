"""One scout per repository in parallel, one triage. The ordering rule is enforced after the model.

strands 1.55's Graph is fail-fast: a scout's model error is re-raised and cancels its siblings,
so `graph(task)` can raise instead of leaving the failure in `result.results`. When that happens we
fall back to reading the scouts individually with per-scout isolation, so a failed scout is dropped
and named (spec 3.6) instead of losing the whole run, and a failed triage surfaces as one plain
line, never a raw stack trace. The fallback runs on its own thread so `run_graph` is safe to call
from a caller that already has an event loop running (an MCP host does).
"""
from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from strands import Agent
from strands.multiagent import GraphBuilder

from .audit import Audit
from .models import Brief, BriefItem, RepoRead, RepoState
from .prompts import SCOUT_SYSTEM, TRIAGE_SYSTEM

ORDER = {"waiting": 0, "will_hurt": 1, "thread": 2}


def rank(items: list[BriefItem]) -> list[BriefItem]:
    return sorted(items, key=lambda i: 0 if i.waiting_on else ORDER[i.kind])


def node_id(repo: str, index: int = 0) -> str:
    """The index keeps two repos that sanitise to the same name apart (my-app and my_app)."""
    return f"scout_{index}_" + re.sub(r"[^a-zA-Z0-9]", "_", repo)


def _run_coroutine(coro):
    """Run a coroutine from a caller that may already be inside a running event loop (MCP hosts are)."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


def scout_agent(state: RepoState, model) -> Agent:
    kwargs = dict(system_prompt=SCOUT_SYSTEM.format(state=state.model_dump_json(), owner=state.owner or "unknown"),
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
    for index, s in enumerate(states):
        nid = node_id(s.name, index)
        b.add_node(scout_agent(s, model), nid)
        b.set_entry_point(nid)
        ids.append(nid)
    b.add_node(triage_agent(model), "triage")
    for nid in ids:
        b.add_edge(nid, "triage")
    b.set_execution_timeout(120)
    b.set_hook_providers([audit])
    return b.build(), ids


def _drop_self(brief: Brief, owner: str) -> Brief:
    """Nobody waits on themselves: an item pointing at the owner is a thread they were pulling."""
    for item in brief.items:
        if item.waiting_on and item.waiting_on.strip().lower().lstrip("@") == owner.strip().lower().lstrip("@"):
            item.waiting_on = None
            item.kind = "thread"
    return brief


def _finish(brief: Brief, failed: list[str], audit: Audit) -> Brief:
    brief.items = rank(_drop_self(brief, audit.target).items)
    brief.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    brief.could_not_see = list(brief.could_not_see) + [f"{n}: the scout could not read it" for n in failed]
    brief.looked_at = list(audit.entries)
    return brief


async def _scout_async(state: RepoState, model, audit: Audit, index: int = 0) -> RepoRead | None:
    audit.node(node_id(state.name, index))
    try:
        result = await scout_agent(state, model).invoke_async("Read your project and report.")
        read = result.structured_output
    except Exception:
        return None
    if not isinstance(read, RepoRead):
        return None
    owner = audit.target.strip().lower().lstrip("@")
    read.waiting = [w for w in read.waiting if w.who.strip().lower().lstrip("@") != owner]
    return read


async def _gather(states: list[RepoState], previous: Brief | None, model, audit: Audit,
                   on_progress: Callable[[str], None]) -> tuple[Brief, list[str]]:
    on_progress(f"reading {len(states)} projects individually")
    reads = await asyncio.gather(*[_scout_async(s, model, audit, n) for n, s in enumerate(states)])
    failed = [s.name for s, r in zip(states, reads) if r is None]
    prompt = "Triage: produce the brief for the owner.\n\nScout reports (JSON):\n" + \
        "\n".join(r.model_dump_json() for r in reads if r is not None)
    if previous is not None:
        prompt += f"\n\nPrevious brief ({previous.generated_at}):\n{previous.model_dump_json()}"
    audit.node("triage")
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
    on_progress(f"reading {len(states)} projects")
    try:
        model = resolve()
    except Exception as exc:
        raise RuntimeError("Standup could not finish the brief (model configuration)") from exc
    try:
        graph, ids = build_graph(states, model, audit)
        task = "Scouts: read your project and report. Triage: produce the brief for the owner."
        if previous is not None:
            task += f"\n\nPrevious brief ({previous.generated_at}):\n{previous.model_dump_json()}"
        result = graph(task)
    except Exception as exc:
        audit.note("first pass stopped early; reading projects individually", target=exc.__class__.__name__)
        return _run_coroutine(_gather(states, previous, model, audit, on_progress))
    failed = [s.name for s, nid in zip(states, ids)
              if nid not in result.results or result.results[nid].status.name != "COMPLETED"]
    node = result.results.get("triage")
    brief = getattr(getattr(node, "result", None), "structured_output", None)
    if not isinstance(brief, Brief):
        raise RuntimeError("Standup could not finish the brief (no structured output)")
    return _finish(brief, failed, audit), failed
