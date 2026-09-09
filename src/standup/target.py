"""Decide whether a target is a folder on disk or a GitHub handle."""
from __future__ import annotations

from pathlib import Path


def is_path(target: str) -> bool:
    if target.startswith((".", "/", "~")):
        return True
    return Path(target).expanduser().exists()


def kind(target: str) -> str:
    return "path" if is_path(target) else "handle"
