"""Standup as an MCP tool for Claude, Cursor and any MCP host. Read-only."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .pipeline import run_standup
from .render import brief_to_text

mcp = FastMCP("standup")


@mcp.tool()
def standup(target: str) -> dict:
    """Triage someone's software projects and say what to do first.

    Call this when a person asks what to work on, what they left unfinished, who is waiting on them,
    or wants a standup across their repositories. `target` is a public GitHub handle or organisation
    (e.g. "yannvr"), or a local folder path. Read-only: it never writes to GitHub or the disk beyond a
    small cache. Returns up to three items with evidence, action and minutes, plus what it looked at.
    """
    brief = run_standup(target)
    out = brief.model_dump()
    out["text"] = brief_to_text(brief)
    return out


def main() -> None:
    mcp.run()
