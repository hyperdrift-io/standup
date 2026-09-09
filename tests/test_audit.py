from strands.hooks.registry import HookRegistry
from strands.hooks.events import BeforeNodeCallEvent

from standup.audit import Audit


def test_note_and_node_events_are_recorded():
    a = Audit(target="yannvr")
    a.note("read 9 public repos", "yannvr")
    reg = HookRegistry()
    a.register_hooks(reg)
    reg.invoke_callbacks(BeforeNodeCallEvent(source=None, node_id="scout_repo1"))
    assert [e.what for e in a.entries] == ["read 9 public repos", "ran scout_repo1"]
    assert all(e.when.endswith("Z") for e in a.entries)
