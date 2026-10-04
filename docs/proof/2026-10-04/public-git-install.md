# Public Git installation verification

The documented MCP command installed and initialized successfully on 2026-10-04:

```bash
uvx --from 'git+https://github.com/hyperdrift-io/standup@mcp-preview-0.3.1' standup-mcp
```

The probe used a fresh UV cache and temporary working directory. Global and system Git configuration were disabled, the credential helper was empty, terminal prompts were disabled, and no GitHub token, SSH agent or model credentials were passed to the process. This was a public HTTPS source install, not an editable checkout.

The annotated preview tag resolved to `9b940b2d5fd13a01aadd47602fbe525ce8fd84be`. Installation plus MCP initialization and tool listing completed in 16.820 seconds on Python 3.12.14. The installed package reported version 0.3.1; `standup` advertised its native output schema.

All seventeen installed runtime Python files matched the exact file fingerprints from the wheel used for the previous live MCP call (`7f72fc61015f28027d91a3eced3a32e31eff26c91e12d3f1b24b2bdb85ac9540`). No third paid model call was made. Full protocol, dependency-version, resolved-commit and fingerprint evidence is in `public-git-install.json`.

This verifies that another user can retrieve and start the documented preview package. It does not resolve the evidence-quality findings in `final-run/README.md`, establish user adoption, or claim a PyPI/MCP Registry listing. Promotion remains held.
