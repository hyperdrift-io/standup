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
    if a.previous and a.previous.exists():
        store.save(Brief.model_validate_json(a.previous.read_text()))
    brief = run_standup(a.target, on_progress=lambda m: print(f"… {m}", file=sys.stderr))
    print(brief.model_dump_json(indent=1) if a.json else brief_to_text(brief))
    return 0
