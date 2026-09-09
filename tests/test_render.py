from standup.models import Brief, BriefItem, LookedAt
from standup.render import brief_to_text


def test_text_has_items_evidence_minutes_and_audit():
    b = Brief(target="yannvr", standing="Main is green.", beyond_tonight="Triage the issues.",
              generated_at="2026-09-09T10:00:00Z", could_not_see=["private repos"],
              looked_at=[LookedAt(when="2026-09-09T10:00:00Z", what="read 9 public repos", target="yannvr")],
              items=[BriefItem(title="Answer alice", evidence="PR #4 open 12 days", action="review it", minutes=15,
                               kind="waiting", waiting_on="alice", repo="proj")])
    text = brief_to_text(b)
    assert "Main is green." in text
    assert "1. Answer alice" in text and "PR #4 open 12 days" in text and "15 minutes" in text
    assert "alice is waiting" in text
    assert "Could not see: private repos" in text
    assert "read 9 public repos" in text
