"""Records what Standup looked at, so read-only is shown rather than claimed."""
from __future__ import annotations

from datetime import datetime, timezone

from strands.hooks.events import BeforeNodeCallEvent
from strands.hooks.registry import HookProvider, HookRegistry

from .models import LookedAt


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Audit(HookProvider):
    def __init__(self, target: str):
        self.target = target
        self.entries: list[LookedAt] = []

    def note(self, what: str, target: str | None = None) -> None:
        self.entries.append(LookedAt(when=_now(), what=what, target=target or self.target))

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeNodeCallEvent, self._on_node)

    def _on_node(self, event: BeforeNodeCallEvent) -> None:
        self.note(f"ran {event.node_id}")
