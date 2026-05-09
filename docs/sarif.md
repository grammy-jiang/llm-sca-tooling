# SARIF static-analysis evidence

Phase 6 makes SARIF v2.1.0 alerts first-class graph evidence. Alerts are stored
as static-analysis facts, bound to indexed files/symbols where possible, and
emitted as `warned_by` graph edges. They are not verdicts.

## Components

- `llm_sca_tooling.sarif.parser` parses SARIF v2.1.0 and resolves artifact URIs
  to repo-relative paths.
- `llm_sca_tooling.sarif.normalizer` maps producer-specific severities, CWE
  tags, rule families, and predicate IDs into stable normalized models.
- `llm_sca_tooling.sarif.store.SarifRunStore` persists normalized runs, rules,
  alerts, and deltas in the workspace SQLite database.
- `llm_sca_tooling.sarif.binding.AlertBinder` binds alerts to graph file and
  symbol nodes.
- `llm_sca_tooling.sarif.warned_by.WarnedByEmitter` creates `sast_rule` and
  `sarif_alert` nodes plus `warned_by` edges.
- `run_static_analysis` imports external SARIF or runs configured analysers and
  updates `code-intelligence://sarif/{repo}` resources.

## MCP resources

- `code-intelligence://sarif/{repo}` lists SARIF runs for a repository.
- `code-intelligence://sarif/{repo}/{run_id}` returns normalized rule summaries,
  severity counts, alert summaries by file, delta summary, and raw SARIF
  artefact metadata.

## Safety

Semgrep, Bandit, and CodeQL adapters use explicit subprocess argument lists.
Registry rulesets that require network are rejected in offline mode, and CodeQL
is disabled by default.
