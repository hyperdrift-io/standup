"""Records what Standup looked at, so read-only is shown rather than claimed.

The same entries drive the page's progress lines: `on_note` is the live feed, `entries` the record.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from strands.hooks.events import BeforeNodeCallEvent
from strands.hooks.registry import HookProvider, HookRegistry

from .models import LookedAt


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Audit(HookProvider):
    def __init__(self, target: str, on_note: Callable[[str], None] | None = None, expected: int = 0):
        self.target = target
        self.entries: list[LookedAt] = []
        self.on_note = on_note
        self.expected = expected  # how many scouts to expect, for "scout 4 of 12"
        self.scouts = 0

    def _say(self, line: str) -> None:
        if self.on_note is not None:
            self.on_note(line)

    def note(self, what: str, target: str | None = None) -> None:
        self.entries.append(LookedAt(when=_now(), what=what, target=target or self.target))
        self._say(what)

    def node(self, node_id: str) -> None:
        """A graph node started: recorded by its id, said in words."""
        self.entries.append(LookedAt(when=_now(), what=f"ran {node_id}", target=self.target))
        if node_id == "triage":
            self._say("choosing what matters most")
            return
        self.scouts += 1
        self._say(f"scout {self.scouts} of {self.expected}" if self.expected else f"scout {self.scouts}")

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeNodeCallEvent, self._on_node)

    def _on_node(self, event: BeforeNodeCallEvent) -> None:
        self.node(event.node_id)
