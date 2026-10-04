# Final-source clean-install MCP probe

Recorded 2026-10-04. Installation and MCP protocol checks passed. The live brief still contains unsupported evidence wording, documented below. This is one operator-run probe, not a user-adoption result or a published-package check.

## Artifact

- `standup_agent-0.3.1-py3-none-any.whl`, SHA-256 `7f72fc61015f28027d91a3eced3a32e31eff26c91e12d3f1b24b2bdb85ac9540`.
- Built from the release worktree; source fingerprints are in `installation.json`. Later source changes need their own artifact-specific verification.
- Fresh temporary environment: Python 3.12.14, MCP 1.30.0, Strands Agents 1.57.2, Google GenAI 2.28.0.
- All nine static assets included. Four installed entry points: `standup`, `standup-mcp`, `standup-agent`, `standup-web`.
- The base wheel installed with only declared runtime dependencies. The existing declared `dev` extra was then installed for the existing suite; no new dependency was added to the project.
- Credentials remained in process memory and environment. State was isolated; only `trekhleb.json` was written to the temporary state directory. Vertex project identifiers are redacted from diagnostics.

## MCP protocol

Both executable aliases were launched from a temporary working directory using the installed wheel, with the real Python MCP SDK. They exposed matching `standup` input and native output schemas.

| Executable | Operation | Result | Elapsed |
| --- | --- | --- | ---: |
| `standup-mcp` | `initialize` | Success | 0.528 s |
| `standup-mcp` | `tools/list` | Native output schema | 0.001 s |
| `standup-agent` | `initialize` | Success | 0.414 s |
| `standup-agent` | `tools/list` | Same native output schema | 0.001 s |
| `standup-agent` | `tools/call`, target `trekhleb` | `isError=false`; native structured result | 43.808 s |

The complete session took 44.973 seconds. Native `structuredContent` validated against the advertised JSON Schema. It contains three items and fourteen audit entries: one read of twelve public repositories, twelve scouts and one triage run. The brief explicitly says it did not read full discussions. This fixes the first run's missing native structured-output contract.

`brief.json`, `brief.txt` and `protocol.json` preserve the returned words without correcting them.

## Remaining evidence-quality findings

The new PR action correctly says to inspect the diff and tests before deciding whether to merge. Two other prompt corrections did not reliably hold in the live result:

1. The brief says PRs 2220 and 2219 have been waiting eleven days, and issue 103 has been open thirty-nine days. The source supplies **days since last update**, not verified waiting time or creation age. PR 2219's different creation and update timestamps are retained in `../first-run/reference-checks.json`. Issue 103's sampled source field is `updatedAt=2026-08-26T02:27:20Z`; it does not establish the opening date.
2. The opening sentence says CI builds are passing across all active repositories. The source snapshot in `../github-baseline.json` has successful default-branch CI for five of the twelve selected repositories; seven have no CI rollup. Missing CI is not evidence of passing CI.

Issue 103 has zero comments in the sampled input, so this run's no-owner-response statement for that particular issue does not demonstrate a failure of the comment-count correction. The broader discussion-reading limit remains accurately stated.

These findings limit claims about automated recommendation quality even though clean installation, both aliases and native MCP output work. No further model call was made to obtain a better-looking sample.

## Existing suite

`<fresh-venv>/bin/python -m pytest -q`: **79 passed**, one warning, 9.73 seconds reported by pytest (10.032 seconds including process startup). The warning is Starlette's deprecation of its current `httpx` test-client integration. It did not fail the gate; no replacement dependency was introduced. Full output is in `pytest.txt` and command/status metadata in `pytest.json`.

No source edits, Git mutations, GitHub writes, package publishing, or social actions were performed by this verification.
