"""One JSON file per handle: the previous brief, so the next one can say what changed."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .models import Brief


def _dir() -> Path:
    d = Path(os.environ.get("STANDUP_STATE", ".standup")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(target: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", target.lower()).strip("-") or "root"


def load(target: str) -> Brief | None:
    p = _dir() / f"{_key(target)}.json"
    if not p.exists():
        return None
    try:
        return Brief.model_validate_json(p.read_text())
    except ValueError:
        return None


def save(brief: Brief) -> Path:
    p = _dir() / f"{_key(brief.target)}.json"
    p.write_text(brief.model_dump_json(indent=1))
    return p


def sweep(days: int = 7) -> int:
    cutoff = time.time() - days * 86400
    removed = 0
    for p in _dir().glob("*.json"):
        if p.stat().st_mtime < cutoff:
            p.unlink()
            removed += 1
    return removed
