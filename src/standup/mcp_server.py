"""Standup as an MCP tool for Claude, Cursor and any MCP host. Read-only."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from .pipeline import run_standup
from .render import brief_to_text
from .models import Brief


class StandupResult(Brief):
    text: str

mcp = FastMCP("standup")


@mcp.tool()
async def standup(target: str) -> StandupResult:
    """Triage someone's software projects and say what to do first.

    Call this when a person asks what to work on, what they left unfinished, who is waiting on them,
    or wants a standup across their repositories. `target` is a public GitHub handle or organisation
    (e.g. "hyperdrift-io"), or a local folder path. Read-only: it never writes to GitHub or the disk beyond a
    small cache. Returns up to three items with evidence, action and minutes, plus what it looked at.
    """
    # The run is a minute of blocking work with its own event loop inside; keep the server's loop free.
    brief = await asyncio.to_thread(run_standup, target)
    return StandupResult(**brief.model_dump(), text=brief_to_text(brief))


def main() -> None:
    mcp.run()
