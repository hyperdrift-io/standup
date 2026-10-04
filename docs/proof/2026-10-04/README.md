# Standup installation and comparison

Standup's MCP installs and runs independently of the HD checkout. It has not
passed the recommendation-quality gate for wider promotion. The installation
repair is an evaluation build; no independent adoption is claimed.

## What changed

- Both `standup-mcp` and the Registry-compatible `standup-agent` executable
  expose the same tool. The result has a native MCP output schema and structured
  content as well as readable text.
- GitHub handle queries explicitly request public repositories, irrespective
  of the token's wider permissions. Local filesystem targets remain local.
- The README supplies a versioned public Git installation. It no longer claims
  an available PyPI distribution or official Registry listing.
- The package README includes the Registry's ownership marker. Tag/package/
  manifest versions and the matching executable are checked before publishing;
  the installed wheel runs the existing tests before any PyPI upload.
- Prompts distinguish last-update age from creation or waiting time and require
  diff/test inspection before deciding to merge. The live result shows that
  these instructions alone do not reliably ground every claim.

## Observed results

| Check | First wheel | Revised wheel |
| --- | --- | --- |
| Fresh non-editable install | Passed | Passed |
| MCP initialization and discovery | Passed | Passed for both aliases |
| Native output schema and structured content | Absent | Passed |
| Live `standup(trekhleb)` | 57.905 seconds | 43.808 seconds |
| Reported coverage | 12 repositories, 14 audit entries | 12 repositories, 14 audit entries |
| Evidence language | Incorrect submission ages | Still overstates waiting/open ages and CI coverage |
| Merge advice | Premature merge recommendations | Inspect diffs and tests before deciding |

The existing suite passed: 79 tests, one Starlette/httpx deprecation warning.
These are two individual runs on the same public account, not a speed benchmark,
a broad accuracy estimate, or customer adoption. Model-provider costs were not
measured. Source fingerprints and artifact hashes are recorded per run.

The [direct GitHub read](direct-github-read.md) was written before seeing the
first MCP result. It selected the two concrete algorithm fixes, a blocked-user
report and a small documentation correction. The revised MCP result also
selected the algorithm fixes, but no superior prioritisation was established.
Its convenience is aggregating and formatting a bounded read in one tool call;
the host still needs GitHub access plus separate model credentials.

## Decision

Keep the working Git installation available for evaluation. Hold PyPI/Registry
promotion and flagship positioning. The next quality comparison should test
the same prioritisation instructions with the host's existing GitHub tools,
alongside a way to tie every displayed fact to an actual source field. Another
prompt-only revision is not sufficient release evidence. Further model-layer
or tool expansion needs evidence that it improves a real maintainer's decision.

The final result claims CI passes across all active repositories even though
seven selected repositories have no CI rollup in the source snapshot. It also
turns last-update ages into waiting/open ages. These are concrete failures to
resolve, not missing analytics or an assumed lack of demand.

## Retained evidence

- [First run](first-run/README.md): unchanged initial output and source checks.
- [Revised run](final-run/README.md): typed protocol result and release tests.
- [GitHub snapshot](github-baseline.json): bounded public data behind the comparison.

The versioned public Git install receives its own transport check after the
tag is available. A local wheel check alone does not establish that public path.
