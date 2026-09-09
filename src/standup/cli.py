# src/standup/cli.py
"""standup <handle | path>"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import store
from .models import Brief
from .pipeline import run_standup
from .render import brief_to_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="standup", description="Who is waiting on you, what will hurt later, what to do first.")
    p.add_argument("target", nargs="?", default=".", help="a GitHub handle or org, or a folder of repositories")
    p.add_argument("--json", action="store_true", help="print the brief as JSON")
    p.add_argument("--previous", type=Path, help="a previous brief JSON to compare against")
    a = p.parse_args(argv)
    if a.previous and not a.previous.exists():
        print(f"… no previous brief at {a.previous}", file=sys.stderr)
    elif a.previous:
        text = a.previous.read_text().strip()
        if text:
            try:
                store.save(Brief.model_validate_json(text))
            except ValueError:
                print("… ignoring --previous: not a brief", file=sys.stderr)
    try:
        brief = run_standup(a.target, on_progress=lambda m: print(f"… {m}", file=sys.stderr))
    except Exception as exc:  # one plain line, whatever broke; never a traceback
        message = str(exc).strip() or exc.__class__.__name__
        print(message if message.startswith("Standup") else f"Standup could not finish: {message}",
              file=sys.stderr)
        return 1
    print(brief.model_dump_json(indent=1) if a.json else brief_to_text(brief))
    return 0
