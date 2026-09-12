# Standup

> **Inherits**: [Hyperdrift workspace AGENTS.md](../../../AGENTS.md) (`~/dev/hyperdrift/AGENTS.md`). Read it first; this file adds Standup-specific context only.
>
> **Voice Covenant**: every user-facing surface, including the agent's generated standup, inherits `meta/PHILOSOPHY.md` #8 "Speak to Enable" — enable, never diminish; strengths first.

## Overview

Standup takes a GitHub handle, reads that person's public repositories, and hands back three things to do first — who is waiting, the evidence it saw, and how long each takes. Live at https://standup.hyperdrift.io (port 3016, per `infra/group_vars/apps.yml`). Built with the Strands Agents SDK for the Agents for Humans Hackathon; load the `contest` skill for submission or post-contest work.

## Product boundary

- **Read-only.** Standup reads repositories and reports what it looked at; it never writes to GitHub.
- Every recommendation carries its evidence. Keep the audit trail (`src/standup/audit.py`) visible in every surface.

## Stack

- Python ≥ 3.10 package in `src/standup/`: `pipeline.py` and `graph.py` (agent flow), `sources/github.py` and `sources/local.py`, `render.py`, `store.py`
- Surfaces: CLI (`cli.py`, `python -m standup`), web (`web.py`, Starlette), MCP server (`mcp_server.py`), and a GitHub Action (`action.yml`)
- Model access through Gemini (`model.py`); `mcp` stays on 1.x until the server is ported to 2.x (see `pyproject.toml`)

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest            # tests/
.venv/bin/python -m standup # CLI
.venv/bin/python -m standup.web
```

Production runs `.venv/bin/python -m standup.web` under PM2 with `interpreter: none`, which does not inject `.env`; the web entrypoint loads it itself.
