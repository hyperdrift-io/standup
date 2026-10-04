# First clean-install MCP probe

Recorded on 2026-10-04. This proves the locally built wheel worked through a real MCP client; it does not establish a PyPI publication, registry adoption, or independent user success.

## Artifact and environment

- Built `standup_agent-0.3.1-py3-none-any.whl` from the in-progress release source based on `7bd66cc`. Exact source fingerprints are in `installation.json`.
- Wheel SHA-256: `f2ad7713c4f6de0b166bbd04b497302be634f50cb05f5bd34fdd7d88f28075f2`.
- Fresh temporary virtual environment, Python 3.12.14; installed the wheel and its declared dependencies with existing `uv`. No editable install and no source checkout on the module path.
- MCP 1.30.0, Strands Agents 1.57.2, Google GenAI 2.28.0. Full installed versions are recorded.
- All nine static assets were present, including the font, CSS, JavaScript and image assets. The `standup`, `standup-mcp` and `standup-web` entry points existed.
- Model credentials were loaded only into process memory from the approved local environment file. GitHub authentication came from `gh auth token`; no credential values are included. State used a fresh temporary directory and produced only `trekhleb.json`.

## Protocol result

The client used the Python MCP SDK's `stdio_client` and `ClientSession`, launching the installed `standup-mcp` executable from a temporary working directory.

| Operation | Result | Elapsed |
| --- | --- | ---: |
| `initialize` | Success | 1.374 s |
| `tools/list` | One tool, `standup` | 0.001 s |
| `tools/call`, target `trekhleb` | `isError=false`; three brief items | 57.905 s |
| Complete protocol session | Success | 59.438 s |

The response records twelve public repositories, twelve scout runs and one triage run: fourteen audit entries including the source read. `could_not_see` is empty. This is the tool's coverage report, not an independent guarantee that every recommendation is correct.

The first wheel returned a JSON object inside text content. `structuredContent` was null and the tool had no `outputSchema`. `brief.json` is the JSON extracted from that exact text response and validated against the installed `Brief` model; `brief.txt` is its unedited rendered text. The release source was subsequently being updated by the main agent, so this artifact does not verify later changes or entry-point aliases.

## Evidence quality finding

The three recommended references exist and were open when checked using `gh pr view` / `gh issue view`. Two time claims are inaccurate:

- PR 2191 is described as submitted two days earlier. GitHub reports creation on 2026-07-07 and last update on 2026-10-02.
- PR 2219 is described as submitted eleven days earlier. GitHub reports creation on 2026-09-19 and last update on 2026-09-22.

The source derives its `days` field from `updatedAt`, which the model described as submission age. This is a recommendation-factuality issue, separate from successful installation and protocol execution. The original brief is preserved without rewriting it. `reference-checks.json` contains the public metadata used for this comparison.

## Files

- `installation.json`: artifact hash, source fingerprints, dependency versions, assets and entry points.
- `protocol.json`: complete initialized/listed/called protocol responses and elapsed times.
- `brief.json` and `brief.txt`: the first live result, unchanged.
- `server-stderr.txt`: sanitized server diagnostics; no server error was reported. The Vertex project identifier is redacted.
- `reference-checks.json`: public metadata for the recommended GitHub references.

No GitHub writes, posting, package publishing, broad test suite, or source modification was performed by this probe. Later packaging or protocol changes require a new artifact-specific check.
