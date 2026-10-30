# Standup

> Inherits `~/dev/hyperdrift/AGENTS.md`.

## Overview

Standup takes a GitHub handle, reads that person's public repositories, and hands back three things to do first — who is waiting, the evidence it saw, and how long each takes. Live at https://standup.hyperdrift.io (port 3016, per `infra/group_vars/apps.yml`). Built with the Strands Agents SDK.

POC (founder, 29 October 2026). Agents for Humans entry, submitted 14 September 2026; outcome in `~/dev/hyperdrift/.growth/contests/ledger.jsonl`.

## Product boundary

- **Read-only.** Standup reads repositories and reports what it looked at; it never writes to GitHub.
- Every recommendation carries its evidence. Keep the audit trail (`src/standup/audit.py`) visible in every surface.
- GitHub handle reads explicitly filter public repositories, even with a token that can read private ones. Local folders remain an explicitly selected local capability.
- Thread ages are last-update ages; counts do not establish who replied, and an open PR does not establish merge readiness. Preserve these evidence limits in every brief.

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

## MCP distribution

`standup-mcp` and `standup-agent` expose the same typed MCP result; the latter
matches the distribution name for Registry clients. Keep `pyproject.toml`,
`server.json` and the release tag on the same version. Verify a non-editable
installation through initialize, discovery and an actual call. A manifest or
publish workflow alone is not publication: check PyPI and the Registry before
claiming availability. Tagged Git source is the documented installation path
while those checks are pending. Retain actual results and their limits in
`docs/proof/`; transport success is separate from recommendation quality.

## Design

Founder-approved Clear Line (11 September 2026) and Three stops mark (13 September). `DESIGN.md` is the contract; brand assets in `src/standup/static/`.
Real SSE owns progress; motion is optional and never stands in for it.
