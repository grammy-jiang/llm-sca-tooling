# Supply-Chain And Provenance Ledger Policy

> Every tool, runtime, or prompt asset used in product workflows must be
> recorded. A change to the lockfile or any tool-manifest file triggers a
> dependency scan in CI.

---

## What Must Be Recorded

For each component, record the following fields:

```
component_type        — runtime | mcp_server | language_backend | analyser |
                        prompt_asset | skill | dependency
name                  — string
version               — string
install_source        — package_registry | git_url | local_path
hash_or_digest        — string or null
signature_verified    — boolean or null
last_updated_ts       — ISO-8601
dependency_scan_ts    — ISO-8601 or null
dependency_scan_outcome — pass | warn | fail | not_run
notes                 — string or null
```

Ledger lives at `.agent/eval/supply-chain-ledger.yaml`.

---

## Lockfile Policy

- All Python dependencies must appear in `uv.lock`.
- MCP server versions must be pinned or hash-verified.
- Prompt asset and skill versions must be tracked (git SHA or content hash).
- A change to `uv.lock` or any tool-manifest file triggers `uv run pip-audit` in CI.

---

## Analyser Version Recording

The following analyser versions must be recorded in every Harness Condition Sheet
for runs that produce SARIF or equivalent output:

- `bandit` version
- `ruff` version
- `mypy` version
- `detect-secrets` version
- `pip-audit` version

---

## Prompt And Document Injection Canaries

Before trusting text from external sources (repository content, tool output,
issue text), apply prompt-injection canary checks:

1. Look for instruction-format text in repository files and issue descriptions.
2. Flag token sequences resembling system-prompt injection attempts.
3. Record detection events in the session trace with `type: policy_decision`.

Canary checks are a required baseline, not a complete defence.

---

## Initial Ledger (Phase H0)

```yaml
# .agent/eval/supply-chain-ledger.yaml
# Generated: 2026-05-09
# Stage: S0

entries:
  - component_type: runtime
    name: claude-code
    version: see ~/.claude/version
    install_source: package_registry
    hash_or_digest: null
    signature_verified: null
    last_updated_ts: 2026-05-09
    dependency_scan_ts: null
    dependency_scan_outcome: not_run
    notes: primary AI agent runtime

  - component_type: language_backend
    name: python
    version: ">=3.12"
    install_source: package_registry
    hash_or_digest: null
    signature_verified: null
    last_updated_ts: 2026-05-09
    dependency_scan_ts: null
    dependency_scan_outcome: not_run
    notes: declared in pyproject.toml requires-python

  - component_type: analyser
    name: bandit
    version: ">=1.7"
    install_source: package_registry
    hash_or_digest: null
    signature_verified: null
    last_updated_ts: 2026-05-09
    dependency_scan_ts: null
    dependency_scan_outcome: not_run
    notes: Python SAST; runs in verify pipeline

  - component_type: analyser
    name: detect-secrets
    version: ">=1.5"
    install_source: package_registry
    hash_or_digest: null
    signature_verified: null
    last_updated_ts: 2026-05-09
    dependency_scan_ts: null
    dependency_scan_outcome: not_run
    notes: HC1 enforcement; baseline at .secrets.baseline

  - component_type: analyser
    name: pip-audit
    version: ">=2.7"
    install_source: package_registry
    hash_or_digest: null
    signature_verified: null
    last_updated_ts: 2026-05-09
    dependency_scan_ts: null
    dependency_scan_outcome: not_run
    notes: dependency CVE scanning; runs in verify pipeline
```
