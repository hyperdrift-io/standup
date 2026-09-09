"""Brief to plain text, for the CLI, the Action issue and the MCP result."""
from __future__ import annotations

from .models import Brief


def brief_to_text(b: Brief) -> str:
    lines = [b.standing, ""]
    for n, it in enumerate(b.items, 1):
        lines.append(f"{n}. {it.title}  ({it.repo})")
        if it.waiting_on:
            lines.append(f"   {it.waiting_on} is waiting.")
        lines.append(f"   Evidence: {it.evidence}")
        lines.append(f"   Action:   {it.action}")
        lines.append(f"   Estimate: {it.minutes} minutes")
        lines.append("")
    lines.append(f"Beyond tonight: {b.beyond_tonight}")
    if b.could_not_see:
        lines.append("Could not see: " + "; ".join(b.could_not_see))
    if b.looked_at:
        lines.append("")
        lines.append("What Standup looked at (read-only):")
        lines += [f"  {e.when}  {e.what}" for e in b.looked_at]
    return "\n".join(lines)
