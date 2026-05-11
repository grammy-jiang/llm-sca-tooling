# LLM-SCA Tooling Phase 6 Implementation Plan: SARIF and Static Analysis Layer

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 6 - SARIF and Static Analysis Layer  
> Primary objective: make static-analysis alerts first-class graph evidence by implementing a SARIF v2.1.0 parser and normalizer, a SARIF run store, alert-to-graph binding, `warned_by` graph edges, adapters for Semgrep, Bandit, optional CodeQL, and optional external SARIF import, rule-family normalization, alert fingerprinting, and a SARIF delta utility — then expose the results through the `run_static_analysis` MCP tool and the `code-intelligence://sarif/{repo}/{run_id}` MCP resource.

---

## 1. Phase Summary

Phase 5 expanded the deterministic graph across Python, JavaScript/TypeScript, and C/C++. Phase 6 layers static-analysis evidence on top of that graph. Static-analysis alerts from tools such as Semgrep, Bandit, and CodeQL are not verdicts — they are evidence nodes that, once bound to graph symbols, allow fault localisation, patch review, blast-radius, and SAST repair workflows to reason about which parts of the code have already been flagged by a deterministic rule.

The central rule for this phase is:

```text
SARIF alerts are evidence, not conclusions.
An alert bound to a graph node raises the suspicion weight on that node
and enables the warned_by edge type.
It does not constitute a verdict.
The graph must keep SAST facts separate from verdicts at all times.
```

Phase 6 should implement:

- SARIF v2.1.0 data model and parser.
- Severity and rule-family normalization.
- SARIF run store.
- Alert fingerprinting for identity-stable delta comparison.
- Alert-to-file and alert-to-symbol graph binding.
- `warned_by` graph edges from SAST alert nodes to target symbol nodes.
- Semgrep adapter for running Semgrep as a subprocess and ingesting its SARIF output.
- Bandit adapter for Python-specific SAST alerts.
- Optional CodeQL adapter behind a capability flag.
- Optional external SARIF import adapter for SonarQube, GitHub Advanced Security, or project-specific SARIF files.
- Rule metadata and predicate ID extraction.
- SARIF before/after delta utility.
- `run_static_analysis` MCP tool as a task-capable operation.
- `code-intelligence://sarif/{repo}/{run_id}` MCP resource with subscription support.
- SAST delta foundation for Phase 11 patch-review and Phase 12 SAST-repair workflows.

### Architecture Coverage

Phase 6 covers:

- SARIF v2.1.0 analyser-data contract.
- F7 foundation: alert binding infrastructure used by SAST alert repair.
- F6 SAST delta foundation: the before/after delta utility needed by patch review.
- Graph edge type `warned_by`.
- Graph node types `sast_rule` and `sarif_alert`.
- MCP tool `run_static_analysis`.
- MCP resource `code-intelligence://sarif/{repo}/{run_id}`.

### Inherited Paper Anchors

Use these anchors in Phase 6 issues, ADRs, adapter notes, and SARIF delta reports:

- `predicatefix`
- `codecureagent`
- `securefixagent`
- `nullrepair`
- `codeql-rule-multiagent`
- `logiceval`

Adjacent anchors useful for rule-family, CWE normalization, and integration notes:

- `why-llms-fail-secpatch`
- `pvbench`
- `compass`
- `llm4cve`
- `correct-not-safe`

## Technology Stack

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| orjson | `orjson` | >=3.10 | Primary JSON I/O for SARIF files (CodeQL output can be hundreds of MB; orjson avoids GIL pressure and is 2–3x faster than stdlib json) |
| Pydantic v2 | `pydantic` | >=2.0 (`extra="forbid"`) | `SarifResult`, `SarifRun`, `SarifRule`, `AlertNode` models; `model_json_schema()` for schema export; no hand-written `.schema.json` |
| jsonschema | `jsonschema` | >=4.20 | Validates incoming SARIF JSON against the official SARIF v2.1.0 schema committed at `schemas/sarif-schema-2.1.0.json` |
| lxml | `lxml` | >=5.2 | XML parsing for any tool output delivered as XML (e.g. Checkstyle-format SAST reports); configure `XMLParser` with `resolve_entities=False`, `no_network=True` |
| defusedxml | `defusedxml` | >=0.7 | XXE protection layer; required for all untrusted XML sources; `forbid_entities=True` |
| Semgrep | `semgrep` | latest available | Static analysis subprocess; invoked via `asyncio.create_subprocess_exec` with `--sarif` flag; never `subprocess.run` in async paths |
| Bandit | `bandit` | >=1.7 | Code quality pipeline (not verdict); Python-specific SAST; invoked via `asyncio.create_subprocess_exec` with `-f sarif`; never `subprocess.run` in async paths |

Notes:

- There is **no external SARIF library**. The SARIF normalizer lives in `llm_sca_tooling.sarif`. Input SARIF is validated with `jsonschema` against `schemas/sarif-schema-2.1.0.json` before any model construction.
- `asyncio.create_subprocess_exec` is mandatory for all subprocess calls (Semgrep, Bandit, optional CodeQL). `subprocess.run` blocks the asyncio event loop and must never appear in async paths. See also §18.4.
- orjson is used for both reading tool-emitted SARIF and writing normalised SARIF artefacts to the artefact registry.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 6 depends on:

- Phase 1 schemas:
  - Graph node types: `sast_rule`, `sarif_alert`, `file`, `module`, `class`, `function`, `method`.
  - Graph edge types: `warned_by`, `checks`, `fixed_by`.
  - Provenance model with `repo_id`, `git_sha`, `worktree_snapshot_id`, `file`, `span`.
  - Confidence and derivation enums: `analyser`, `parser`, `heuristic`.
  - Evidence-strength ordering.
  - Verdict values: `safe`, `risky`, `unknown`.
  - SARIF reference fields in patch/verdict schema: `sarif_delta_id`.
- Phase 2 stores:
  - Repository registry and snapshot ledger.
  - Graph store for add-node, add-edge, fetch by file/span, fetch by type.
  - Artefact registry for storing raw SARIF JSON files.
  - Operational store for run records and events.
- Phase 3/4/5 indexing:
  - File node IDs per repo-relative path.
  - Symbol node IDs per file/span.
  - Snapshot tracking and freshness state.
  - Build/test evidence records for pre-existing CI/SARIF detection.
- Phase 4 MCP:
  - Task manager for long-running `run_static_analysis`.
  - Notification/subscription infrastructure for `sarif` resource updates.
  - Tool registry and permission descriptor model.

### Phase Outputs

Phase 6 should produce:

- SARIF v2.1.0 data models and parser.
- Normalized SARIF run, alert, and rule models.
- SARIF run store.
- Alert fingerprinting module.
- Alert-to-graph binding module.
- `warned_by` edge emitter.
- Semgrep adapter.
- Bandit adapter.
- Optional CodeQL adapter (gated by capability flag).
- Optional external SARIF import adapter.
- Rule metadata and predicate ID extractor.
- Severity and rule-family normalizer.
- SARIF delta utility.
- `run_static_analysis` MCP tool (task-capable).
- `code-intelligence://sarif/{repo}/{run_id}` MCP resource handler.
- SARIF resource subscription integration.
- Phase 5 `warned_by` edge back-population for existing diagnostic nodes from Pyright and clangd.
- SARIF fixture files and integration test fixtures.

### Non-Goals

Do not implement these in Phase 6:

- SAST alert repair workflow. That is Phase 12.
- Predicate-example retrieval (`get_predicate_examples`). That is Phase 12.
- Offline rule evolution (`evolve_static_rules`). That is Phase 12.
- Patch-risk classification using SARIF delta. That is Phase 11.
- Bug-resolve workflow. That is Phase 13.
- Trained patch-risk ML classifier. That is Phase 18.
- CWE-based vulnerability prior for the patch-risk classifier. That is Phase 11.
- PoC+ validation. That is Phase 11.

Phase 6 produces the SARIF evidence layer. It does not act on alerts to generate patches, compute risk scores, or classify vulnerabilities.

---

## 3. Recommended File Layout

```text
src/evidence_sca/
  sarif/
    __init__.py
    models.py
    parser.py
    normalizer.py
    fingerprint.py
    store.py
    binding.py
    warned_by.py
    delta.py
    resource.py

  sarif/adapters/
    __init__.py
    base.py
    semgrep.py
    bandit.py
    codeql.py
    external_import.py
    sonarqube.py
    ruleset.py

  mcp_server/tools/
    sarif.py

  mcp_server/resources/
    sarif.py

tests/
  sarif/
    fixtures/
      sarif_runs/
        semgrep_python_basic.sarif.json
        semgrep_typescript_basic.sarif.json
        semgrep_cpp_basic.sarif.json
        bandit_basic.sarif.json
        codeql_basic.sarif.json
        external_generic.sarif.json
        sonarqube_export.sarif.json
        delta_before.sarif.json
        delta_after.sarif.json
        malformed.sarif.json
        partial_locations.sarif.json
      rulesets/
        semgrep_python_security.yaml
        semgrep_ts_security.yaml
    adapters/
      test_semgrep_adapter.py
      test_bandit_adapter.py
      test_codeql_adapter.py
      test_external_import.py
      test_sonarqube_adapter.py
      test_ruleset.py
    test_models.py
    test_parser.py
    test_normalizer.py
    test_fingerprint.py
    test_store.py
    test_binding.py
    test_warned_by.py
    test_delta.py
    test_sarif_resource.py
    test_run_static_analysis.py
    test_integration.py
```

---

## 4. SARIF v2.1.0 Data Model And Parser

### 4.1 Scope

SARIF v2.1.0 is the only supported version. Older SARIF versions should be rejected with a typed diagnostic. Future SARIF versions should be handled via a compatibility shim if the schema is backward-compatible.

### 4.2 Core SARIF Data Models

`models.py` defines internal Python representations of SARIF v2.1.0 objects. These are read-only after parsing and serve as the normalized intermediate between raw JSON and the graph store.

Required models and their key fields:

```text
SarifLog
  version : str         # Must be "2.1.0"
  runs : list[SarifRun]
  schema_uri : str | None

SarifRun
  tool : SarifTool
  results : list[SarifResult]
  artifacts : list[SarifArtifact]
  logical_locations : list[SarifLogicalLocation]
  invocations : list[SarifInvocation]
  automation_details : SarifRunAutomationDetails | None
  baseline_guid : str | None
  original_uri_base_ids : dict[str, str]

SarifTool
  driver : SarifToolComponent
  extensions : list[SarifToolComponent]

SarifToolComponent
  name : str
  version : str | None
  semantic_version : str | None
  guid : str | None
  rules : list[SarifReportingDescriptor]
  notifications : list[SarifReportingDescriptor]

SarifReportingDescriptor
  id : str
  name : str | None
  short_description : str | None
  full_description : str | None
  help_uri : str | None
  default_configuration : SarifReportingConfiguration | None
  properties : dict[str, Any]  # raw properties bag; CWE, OWASP, tags extracted later

SarifReportingConfiguration
  enabled : bool
  level : str | None  # error, warning, note, none
  rank : float | None

SarifResult
  rule_id : str | None
  rule_index : int | None
  level : str | None   # error, warning, note, none
  message : str
  locations : list[SarifLocation]
  related_locations : list[SarifLocation]
  code_flows : list[SarifCodeFlow]
  fixes : list[SarifFix]
  suppressions : list[SarifSuppression]
  baseline_state : str | None  # new, updated, absent, unchanged
  fingerprints : dict[str, str]
  partial_fingerprints : dict[str, str]
  work_item_uris : list[str]
  properties : dict[str, Any]  # raw bag; security-severity, precision, tags

SarifLocation
  physical_location : SarifPhysicalLocation | None
  logical_locations : list[SarifLogicalLocation]
  message : str | None

SarifPhysicalLocation
  artifact_location : SarifArtifactLocation
  region : SarifRegion | None

SarifArtifactLocation
  uri : str | None
  uri_base_id : str | None
  index : int | None

SarifRegion
  start_line : int | None
  start_column : int | None
  end_line : int | None
  end_column : int | None
  byte_offset : int | None
  byte_length : int | None

SarifCodeFlow
  thread_flows : list[SarifThreadFlow]
  message : str | None

SarifThreadFlow
  locations : list[SarifThreadFlowLocation]

SarifThreadFlowLocation
  location : SarifLocation | None
  kinds : list[str]
  state : dict[str, Any]

SarifFix
  description : str | None
  artifact_changes : list[SarifArtifactChange]

SarifSuppression
  kind : str  # inSource, external
  status : str | None  # accepted, underReview, rejected
  justification : str | None

SarifArtifact
  location : SarifArtifactLocation
  parent_index : int | None
  length : int | None
  mime_type : str | None

SarifInvocation
  tool_execution_successful : bool | None
  exit_code : int | None
  start_time_utc : str | None
  end_time_utc : str | None
  working_directory : SarifArtifactLocation | None
  tool_execution_notifications : list[SarifNotification]

SarifNotification
  message : str
  level : str | None
  associated_rule : SarifReportingDescriptorReference | None
```

### 4.3 Parser Rules

`parser.py` reads SARIF JSON and produces a `SarifLog`.

Rules:

- Reject version != "2.1.0" with a typed `SarifVersionError`.
- Reject malformed JSON with `SarifParseError`.
- Unknown top-level properties: warn and continue.
- Missing optional fields: use None, not synthetic defaults.
- Do not silently drop results with missing locations.
- Artifact URIs must be resolved to repo-relative paths where possible.
- `uriBaseId` values must be resolved through `originalUriBaseIds` before repo-relative path computation.
- Large SARIF files must be streamable; do not require full in-memory loading for store operations.

### 4.4 Artifact URI Resolution

SARIF artifact URIs may be absolute, relative, or `uriBaseId`-relative.

Resolution rules:

- If `uriBaseId` is `SRCROOT` or equivalent, resolve relative to repo root.
- If URI is an absolute file path, strip the repo root prefix if it matches.
- If URI cannot be resolved to a repo-relative path, mark as `unresolvable` in diagnostics.
- Do not expose absolute host paths in stored records.

### 4.5 Parser Tests

Required tests:

- Valid SARIF v2.1.0 parses correctly.
- Version mismatch raises `SarifVersionError`.
- Malformed JSON raises `SarifParseError`.
- Missing optional fields parse as None.
- Result with no location parses and is preserved.
- `uriBaseId` resolution produces repo-relative paths.
- Absolute path stripping works for repo root match.
- Large SARIF file parses without OOM.

---

## 5. Severity And Rule-Family Normalization

### 5.1 Purpose

Different SARIF producers use different severity vocabulary. `normalizer.py` maps all inputs to a stable normalized set used throughout the system.

### 5.2 Normalized Severity Enum

```text
NormalizedSeverity
  critical       # CVSS >= 9.0 or analyser "error" with security tag
  high           # analyser "error" level or Bandit HIGH/HIGH
  medium         # analyser "warning" level or Bandit HIGH/MEDIUM or MEDIUM/HIGH
  low            # analyser "note" level or Bandit LOW/*
  informational  # level "none" or informational annotations
```

Mapping rules per tool:

- **Semgrep**: `error` → `high`, `warning` → `medium`, `info` → `low`, `note` → `informational`. If `properties.security-severity` is present (CVSS score), upgrade to `critical` when score >= 9.0.
- **Bandit**: Cross-matrix of Bandit severity (HIGH/MEDIUM/LOW) and confidence (HIGH/MEDIUM/LOW). HIGH/HIGH → `high`, HIGH/MEDIUM → `medium`, MEDIUM/HIGH → `medium`, others → `low`.
- **CodeQL**: `error` → `high`, `warning` → `medium`, `recommendation` → `low`, `note` → `informational`.
- **External/Unknown**: treat `error` → `high`, `warning` → `medium`, `note` → `low`, `none` → `informational`.
- If `properties.security-severity` is present as a CVSS string, parse and override with CVSS-based bucketing.

### 5.3 Rule Family Normalization

Map rule IDs and tags to a canonical rule family for cross-analyser correlation.

Canonical rule family identifiers:

- `sql-injection`
- `xss`
- `path-traversal`
- `command-injection`
- `xxe`
- `ssrf`
- `deserialization`
- `null-deref`
- `buffer-overflow`
- `use-after-free`
- `integer-overflow`
- `crypto-weak`
- `hardcoded-secret`
- `insecure-random`
- `improper-auth`
- `missing-auth`
- `privilege-escalation`
- `race-condition`
- `resource-leak`
- `unchecked-return`
- `taint-flow`
- `other`

Sources for family detection:

- CWE tags in rule properties (`cwe`, `cwe-id`, `cwe-ids`).
- OWASP category tags.
- Rule ID pattern matching per analyser (Semgrep rule paths, Bandit test IDs, CodeQL query paths).
- Rule short description keyword matching as fallback.

### 5.4 CWE Extraction

Rules:

- Extract CWE IDs from rule properties in the formats: `CWE-89`, `CWE:89`, `89`.
- Normalize to `CWE-NNN` canonical form.
- Preserve raw CWE string and normalized ID separately.
- Multiple CWEs per rule are preserved as a list.

### 5.5 Predicate ID Extraction

Rules:

- CodeQL stores predicate IDs in result properties as `github/alertNumber` or similar. Extract where available.
- Semgrep rules embed their rule source in `result.ruleId`; the full dotted path is the predicate-equivalent identifier.
- Bandit embeds test IDs (`B101`, `B102`, etc.) as rule IDs; normalize to `BANDIT-B101` form.

These predicate IDs are the link used by Phase 12 `get_predicate_examples` to fetch fix-knowledge from a clean corpus.

### 5.6 Normalization Tests

Required tests:

- Semgrep `error` → `high`.
- Semgrep `properties.security-severity: "9.5"` → `critical`.
- Bandit HIGH/HIGH → `high`.
- Bandit LOW/LOW → `low`.
- CodeQL `warning` → `medium`.
- Unknown tool `error` → `high`.
- CWE extraction handles `CWE-89`, `cwe: 89`, and `CWE:89`.
- Rule family detection from CWE-89 → `sql-injection`.
- Semgrep rule path `python.lang.security.audit.sqli` → `sql-injection`.
- Bandit B105 → `hardcoded-secret`.

---

## 6. SARIF Run Store

### 6.1 Purpose

The SARIF run store persists normalized SARIF runs and provides query interfaces for lookups by repo, analyser, ruleset, snapshot, and time range.

### 6.2 `NormalizedSarifRun`

The run store stores `NormalizedSarifRun` instances, not raw `SarifRun` objects.

```text
NormalizedSarifRun
  run_id : str                 # High-entropy ID assigned by the store
  repo_id : str
  snapshot_id : str
  git_sha : str
  worktree_snapshot_id : str | None
  analyser_id : str            # semgrep, bandit, codeql, external
  analyser_version : str | None
  analyser_name : str
  ruleset_id : str             # Hash of ruleset config
  ruleset_name : str | None
  invocation_start_ts : str | None
  invocation_end_ts : str | None
  invocation_exit_code : int | None
  invocation_successful : bool
  rules : list[NormalizedRule]
  alerts : list[NormalizedAlert]
  invocation_diagnostics : list[str]
  raw_sarif_artifact_ref : ArtifactRef
  produced_by_run_id : str | None   # Link to operational run that triggered this analysis
  delta_from_run_id : str | None    # If this run was computed against a baseline
```

### 6.3 `NormalizedRule`

```text
NormalizedRule
  rule_id : str
  analyser_id : str
  name : str | None
  short_description : str | None
  full_description : str | None
  help_uri : str | None
  raw_severity : str | None
  normalized_severity : NormalizedSeverity
  cwe_ids : list[str]
  owasp_categories : list[str]
  rule_family : str
  predicate_id : str | None
  tags : list[str]
  enabled : bool
  confidence_level : ConfidenceLevel
```

### 6.4 `NormalizedAlert`

```text
NormalizedAlert
  alert_id : str               # Fingerprint-derived stable ID
  run_id : str
  rule_id : str
  analyser_id : str
  raw_level : str | None
  normalized_severity : NormalizedSeverity
  message : str
  file_path : str | None       # Repo-relative primary location
  start_line : int | None
  start_column : int | None
  end_line : int | None
  end_column : int | None
  related_locations : list[AlertLocation]
  code_flows : list[AlertCodeFlow]
  suppressed : bool
  suppression_kind : str | None
  suppression_status : str | None
  suppression_justification : str | None
  fingerprint : str            # Computed stable fingerprint
  raw_fingerprints : dict[str, str]    # From SARIF result
  baseline_state : str | None  # new, updated, absent, unchanged
  bound_file_node_id : str | None
  bound_symbol_node_ids : list[str]
  binding_confidence : ConfidenceLevel
  properties : dict[str, Any]
```

### 6.5 Storage Schema

Recommended storage tables if using Phase 2 SQLite store:

```sql
CREATE TABLE sarif_runs (
  run_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  git_sha TEXT NOT NULL,
  worktree_snapshot_id TEXT,
  analyser_id TEXT NOT NULL,
  analyser_version TEXT,
  analyser_name TEXT NOT NULL,
  ruleset_id TEXT NOT NULL,
  ruleset_name TEXT,
  invocation_start_ts TEXT,
  invocation_end_ts TEXT,
  invocation_exit_code INTEGER,
  invocation_successful INTEGER NOT NULL,
  alert_count INTEGER NOT NULL,
  rule_count INTEGER NOT NULL,
  raw_sarif_artifact_id TEXT,
  produced_by_run_id TEXT,
  delta_from_run_id TEXT,
  created_ts TEXT NOT NULL
);

CREATE TABLE sarif_rules (
  rule_pk TEXT PRIMARY KEY,     -- run_id + ":" + rule_id
  run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  rule_id TEXT NOT NULL,
  analyser_id TEXT NOT NULL,
  name TEXT,
  short_description TEXT,
  normalized_severity TEXT NOT NULL,
  cwe_ids_json TEXT NOT NULL,
  owasp_json TEXT NOT NULL,
  rule_family TEXT NOT NULL,
  predicate_id TEXT,
  tags_json TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  rule_json TEXT NOT NULL
);

CREATE TABLE sarif_alerts (
  alert_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  rule_id TEXT NOT NULL,
  analyser_id TEXT NOT NULL,
  normalized_severity TEXT NOT NULL,
  message TEXT NOT NULL,
  file_path TEXT,
  start_line INTEGER,
  start_column INTEGER,
  end_line INTEGER,
  end_column INTEGER,
  suppressed INTEGER NOT NULL,
  fingerprint TEXT NOT NULL,
  baseline_state TEXT,
  bound_file_node_id TEXT,
  bound_symbol_ids_json TEXT NOT NULL,
  binding_confidence TEXT NOT NULL,
  alert_json TEXT NOT NULL
);

CREATE INDEX idx_sarif_alerts_repo ON sarif_alerts(run_id);
CREATE INDEX idx_sarif_alerts_file ON sarif_alerts(file_path);
CREATE INDEX idx_sarif_alerts_rule ON sarif_alerts(rule_id);
CREATE INDEX idx_sarif_alerts_severity ON sarif_alerts(normalized_severity);
CREATE INDEX idx_sarif_runs_repo ON sarif_runs(repo_id, invocation_start_ts);
```

### 6.6 Query Interface

```text
SarifRunStore
  store_run(run: NormalizedSarifRun) -> str  # Returns run_id
  get_run(run_id: str) -> NormalizedSarifRun | None
  list_runs(repo_id: str, analyser_id: str | None, since_ts: str | None) -> list[SarifRunSummary]
  get_alerts(run_id: str, severity_min: NormalizedSeverity | None) -> list[NormalizedAlert]
  get_alerts_for_file(repo_id: str, file_path: str, active_run_ids: list[str]) -> list[NormalizedAlert]
  get_alerts_for_symbol(symbol_node_id: str) -> list[NormalizedAlert]
  get_latest_run(repo_id: str, analyser_id: str, ruleset_id: str) -> NormalizedSarifRun | None
  delete_run(run_id: str) -> None
```

### 6.7 Store Tests

Required tests:

- Store and retrieve a SARIF run.
- List runs by repo and analyser.
- Get alerts for a file.
- Get alerts filtered by minimum severity.
- Get latest run for repo/analyser/ruleset.
- Delete a run.
- Concurrent store access does not corrupt state.

---

## 7. Alert Fingerprinting

### 7.1 Purpose

Alert fingerprints provide stable identities across analysis runs so that the SARIF delta utility can recognize when the same alert appears in two different runs — even when surrounding line numbers shift due to unrelated code changes.

### 7.2 Fingerprint Fields

The fingerprint must be sensitive to the alert's actual content but insensitive to minor positional noise.

Primary fingerprint input fields:

- Analyser ID.
- Rule ID.
- Repo-relative file path.
- Start line (±N line tolerance is NOT applied; the fingerprint is exact, but deltas use fuzzy matching).
- The alert message normalized for whitespace.
- Code snippet hash if a snippet is present in the SARIF region.

Secondary (partial) fingerprint:

- Rule family.
- Normalized severity.
- Start column if present.

Rules:

- Primary fingerprint: SHA-256 of the canonical concatenation of primary fields, truncated to 16 hex characters.
- Partial fingerprint: SHA-256 of secondary fields, truncated to 8 hex characters.
- Full alert ID: `{analyser_id}:{primary_fingerprint}`.
- If the SARIF result already has a fingerprint in `fingerprints["primaryLocationLineHash"]` or equivalent, preserve it alongside the computed fingerprint without replacing it.

### 7.3 Fingerprint Stability Rules

The fingerprint must remain stable when:

- An unrelated function is added above the alert location (line numbers shift).
- Whitespace-only formatting changes surround the alert.

The fingerprint should change when:

- The rule ID changes.
- The file is renamed or moved.
- The alert message changes in substance.
- The code snippet at the alert location changes.

### 7.4 Fingerprint Tests

Required tests:

- Same alert in two runs produces the same fingerprint.
- Whitespace-only change in surrounding code: same fingerprint.
- Rule ID change: different fingerprint.
- File rename: different fingerprint.
- Alert message change: different fingerprint.
- Code snippet change: different fingerprint.
- Existing SARIF fingerprint is preserved alongside computed fingerprint.

---

## 8. Alert-To-Graph Binding And `warned_by` Edges

### 8.1 Purpose

`binding.py` matches each `NormalizedAlert` to graph nodes so that downstream workflows can traverse from SAST evidence into the symbol graph. `warned_by.py` emits `warned_by` graph edges from `sarif_alert` or `sast_rule` nodes to the bound symbol nodes.

### 8.2 Binding Strategies

Two binding strategies run in order, with results merged:

**File binding** (always attempted):
- Match `alert.file_path` to a `file` graph node with the same repo-relative path.
- Confidence: `parser` for exact path match, `heuristic` for normalized path match.
- If no `file` node exists, record `binding_confidence = none` and emit a diagnostic.

**Symbol binding** (attempted when file binding succeeds):
- Query the graph for all symbol nodes (`class`, `function`, `method`, `variable`) in the matched file.
- Find symbol nodes whose span overlaps or contains the alert region.
- Span overlap rules:
  - The alert start line falls within the symbol's start-to-end line range.
  - Or the alert region is fully contained within the symbol's region.
- Assign highest-overlap symbol as the primary binding.
- Record all overlapping symbols as secondary bindings.
- Confidence: `parser` for full containment, `heuristic` for partial overlap or line-only match.
- If no symbol overlaps, binding is `file-only`.

**Code flow binding** (optional, for taint alerts with code flows):
- Bind each code flow step location independently.
- Emit `related_location` binding results for multi-step alerts.
- Do not elevate code flow bindings to primary bindings.

### 8.3 `warned_by` Graph Edges

`warned_by.py` emits graph edges after binding is computed.

Edge structure:

```text
warned_by edge
  source_node_id : str   # sarif_alert node ID
  target_node_id : str   # bound symbol or file node ID
  edge_type : "warned_by"
  repo_id : str
  git_sha : str
  snapshot_id : str
  confidence : ConfidenceLevel
  derivation : "analyser"
  rule_id : str
  analyser_id : str
  run_id : str
  alert_id : str
  binding_type : "primary" | "secondary" | "file_only"
```

Each bound alert emits at minimum one `warned_by` edge. An alert with multiple overlapping symbols emits one `primary` edge and zero or more `secondary` edges.

### 8.4 `sast_rule` And `sarif_alert` Graph Nodes

Phase 1 defines `sast_rule` and `sarif_alert` as graph node types. Phase 6 populates them.

`sast_rule` node (one per rule per run, or shared across runs by rule ID + analyser):

```text
id
rule_id
analyser_id
analyser_version
name
short_description
normalized_severity
rule_family
cwe_ids
predicate_id
repo_id
run_id
confidence = analyser
derivation = analyser
```

`sarif_alert` node (one per normalized alert):

```text
id
alert_id
rule_id
analyser_id
run_id
file_path
start_line
end_line
normalized_severity
message
suppressed
fingerprint
repo_id
snapshot_id
confidence = analyser
derivation = analyser
```

### 8.5 Binding Rules

- A suppressed alert must still be bound to its file node but should be tagged `suppressed` and its `warned_by` edges should carry the suppression metadata.
- Alerts with no resolvable file path must emit a diagnostic and must not be silently dropped.
- Binding results must reference the snapshot ID of the graph nodes they bind to.
- Mixed snapshots (alert produced against git SHA A, graph built from git SHA B) must be flagged as `mixed_snapshot_binding` in the alert's binding record.

### 8.6 Phase 5 Back-Population

Phase 5 Pyright and clangd adapters already emit diagnostic nodes. Phase 6 must:

- Detect existing `sast_rule`-like diagnostic nodes from Pyright and clangd.
- Normalize them through the SARIF normalizer if they carry SARIF-like data.
- Emit `warned_by` edges for those existing nodes using the binding logic.

This back-population runs as an optional migration step during Phase 6 first-time initialization.

### 8.7 Binding Tests

Required tests:

- Alert on exact file path binds to `file` node.
- Alert spanning a function body binds to that function symbol.
- Alert at file level (no line) binds to file only.
- Alert with overlapping multiple symbols: primary and secondary edges emitted.
- Suppressed alert: bound with suppression tag, `warned_by` edge present.
- Unresolvable file path: diagnostic, no edge, no crash.
- Mixed-snapshot binding: flagged.
- `warned_by` edges round-trip through Phase 1 schema validation.

---

## 9. SARIF Delta Utility

### 9.1 Purpose

`delta.py` compares two `NormalizedSarifRun` instances and classifies each alert into an appearance state. This is the SARIF delta foundation consumed by Phase 11 patch review and Phase 12 SAST repair.

### 9.2 `SarifDelta`

```text
SarifDelta
  before_run_id : str
  after_run_id : str
  repo_id : str
  before_snapshot_id : str
  after_snapshot_id : str
  appeared : list[NormalizedAlert]    # In after, not in before
  disappeared : list[NormalizedAlert] # In before, not in after
  unchanged : list[NormalizedAlert]   # In both, fingerprint matches
  changed : list[AlertChange]         # Same rule/file, different location or severity
  suppressed_in_before : list[NormalizedAlert]
  suppressed_in_after : list[NormalizedAlert]
  delta_id : str
  computed_ts : str

AlertChange
  before_alert : NormalizedAlert
  after_alert : NormalizedAlert
  change_type : AlertChangeType
    # location_shifted, severity_changed, message_changed, suppression_changed

SarifDeltaSummary
  appeared_count : int
  disappeared_count : int
  unchanged_count : int
  changed_count : int
  appeared_by_severity : dict[NormalizedSeverity, int]
  disappeared_by_severity : dict[NormalizedSeverity, int]
  new_critical_or_high_count : int
  fixed_critical_or_high_count : int
```

### 9.3 Alert Matching Algorithm

Alert matching for delta computation:

1. Exact match: `before.fingerprint == after.fingerprint` → `unchanged`.
2. Rule-and-file match with small line drift (±5 lines): candidate for `changed/location_shifted`.
3. Rule-and-file match with different message: `changed/message_changed`.
4. In after only: `appeared`.
5. In before only: `disappeared`.

Rules:

- Exact fingerprint match takes priority over fuzzy matching.
- A single before-alert cannot be matched to more than one after-alert.
- A `changed` alert carries both the before and after representations.
- When SARIF `baselineState` is present in the after run, use it to validate the computed delta.

### 9.4 Delta Use In Downstream Phases

The delta is referenced by:

- Phase 11 patch review via `sarif_delta_id` field in the patch and verdict schema.
- Phase 12 SAST repair to verify the alert disappears after the patch.

Phase 6 must persist deltas and expose them through the SARIF store so later phases can retrieve them by `delta_id`.

```sql
CREATE TABLE sarif_deltas (
  delta_id TEXT PRIMARY KEY,
  before_run_id TEXT NOT NULL,
  after_run_id TEXT NOT NULL,
  repo_id TEXT NOT NULL,
  appeared_count INTEGER NOT NULL,
  disappeared_count INTEGER NOT NULL,
  unchanged_count INTEGER NOT NULL,
  changed_count INTEGER NOT NULL,
  new_critical_high_count INTEGER NOT NULL,
  fixed_critical_high_count INTEGER NOT NULL,
  delta_json TEXT NOT NULL,
  computed_ts TEXT NOT NULL
);
```

### 9.5 Delta Tests

Required tests:

- Identical runs produce zero appeared/disappeared.
- Alert added in after run: appears in `appeared`.
- Alert removed in after run: appears in `disappeared`.
- Alert at shifted line: appears in `changed/location_shifted`.
- Alert severity change: appears in `changed/severity_changed`.
- Alert suppressed in after: suppression tracked.
- Delta persists and is retrievable by `delta_id`.
- `new_critical_or_high_count` is correct.

---

## 10. Semgrep Adapter

### 10.1 Purpose

Semgrep is the primary static analysis tool and supports multiple languages. It is the default analyser for Python, JavaScript/TypeScript, and any language with community or custom rules.

### 10.2 Adapter Design

`semgrep.py` implements `AnalyserAdapterBase`.

```text
SemgrepAdapter
  adapter_id : str = "semgrep"
  
  check_availability() -> AnalyserAvailability
    # Check semgrep CLI is on PATH and report version.

  resolve_ruleset(ruleset_config: RulesetConfig) -> ResolvedRuleset
    # Validate ruleset YAML files or registry rule IDs.
    # Compute ruleset hash for run identity.

  run(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    ruleset: ResolvedRuleset,
    files: list[RepoRelativePath] | None,
    config: SemgrepConfig,
  ) -> SarifLog
    # Execute: semgrep --sarif --output <tempfile> [--include ...] <ruleset> <repo_path>
    # Parse SARIF output.
    # Map SARIF artifact URIs to repo-relative paths.
```

### 10.3 Ruleset Configuration

`ruleset.py` handles ruleset resolution.

Supported ruleset forms:

- Semgrep registry ID: `p/security-audit`, `p/python`, `p/owasp-top-ten`.
- Local YAML rule file path (relative to workspace).
- Inline rule dict.
- Mixed list of the above.

Ruleset hash: SHA-256 of the canonical serialization of resolved rule IDs and versions.

### 10.4 Semgrep Execution

Rules:

- Run Semgrep in a subprocess with `--sarif --output <tempfile>`.
- Set a wall-clock timeout from the tool's budget config.
- Capture stdout and stderr separately.
- Non-zero exit code 1 (findings present) is success. Non-zero codes 2+ are errors.
- Always parse the SARIF file even when Semgrep reports findings.
- Record exit code, stdout (truncated), and stderr (truncated) in invocation diagnostics.
- Do not pass repo absolute path in stored diagnostics; record relative path.
- Semgrep must run with `--no-rewrite-rule-ids` to preserve original rule IDs.
- Set `--quiet` to suppress progress output to stderr.

### 10.5 Network Policy

Rules:

- Semgrep must not download rules at runtime when running in offline mode.
- The HC5 deny-by-default network egress constraint applies.
- Rule files must be pre-fetched and stored locally or in the workspace.
- If a registry rule ID requires network, report `NETWORK_REQUIRED` diagnostic and skip that ruleset unless offline rules are available.

### 10.6 Semgrep Tests

Required tests:

- Availability check returns Semgrep version when installed.
- Availability check returns unavailable when Semgrep not found.
- Ruleset YAML validates.
- Semgrep run produces SARIF for Python fixture repo.
- Semgrep run with no findings produces zero-alert SARIF, not error.
- Non-zero exit code 2+ produces error diagnostic, not crash.
- Network policy respected: offline mode does not download rules.
- Subprocess timeout produces `ANALYSER_TIMEOUT` diagnostic.
- Absolute paths stripped from stored invocation records.

---

## 11. Bandit Adapter

### 11.1 Purpose

Bandit is the standard Python-specific security linter. It focuses on common Python security antipatterns.

### 11.2 Adapter Design

`bandit.py` implements `AnalyserAdapterBase`.

```text
BanditAdapter
  adapter_id : str = "bandit"
  
  check_availability() -> AnalyserAvailability
    # Check bandit CLI or Python importability and report version.

  run(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    ruleset: ResolvedRuleset,
    files: list[RepoRelativePath] | None,
    config: BanditConfig,
  ) -> SarifLog
    # Execute: bandit -r <path> -f sarif -o <tempfile> [test filter]
    # Parse SARIF output.
    # Fall back to JSON format conversion if SARIF output is not available.
```

### 11.3 Bandit SARIF Support

Bandit 1.7.5+ supports `-f sarif`. Earlier versions output JSON.

Compatibility rules:

- If `bandit --format sarif` is supported, use it directly.
- If not supported, use `-f json` and convert Bandit JSON to a synthetic SARIF document using a minimal translator.
- The synthetic SARIF must carry analyser name, version, rule IDs, locations, and message.
- Mark synthetic SARIF documents with `analyser_synthetic_sarif: true` in run metadata.

### 11.4 Bandit Rule Selection

Bandit test IDs use the pattern `B101`–`B799`. The adapter should:

- Support specifying test IDs to run (`-t B101,B102`).
- Support specifying test IDs to skip (`-s B101`).
- Default to running all tests unless a ruleset config restricts them.

### 11.5 Bandit Tests

Required tests:

- Availability check returns Bandit version when installed.
- Bandit run produces SARIF/synthetic-SARIF for Python fixture.
- Bandit HIGH/HIGH alert normalizes to `high`.
- Bandit rule ID B105 maps to rule family `hardcoded-secret`.
- Synthetic SARIF fallback produces valid `NormalizedSarifRun`.
- Bandit timeout produces diagnostic.

---

## 12. Optional CodeQL Adapter

### 12.1 Purpose

CodeQL provides interprocedural taint and control-flow analysis beyond what Semgrep and Bandit can offer. It requires a compiled database and is therefore more expensive to run.

### 12.2 Capability Flag

```text
CODEQL_BACKEND_ENABLED : bool
  # Controlled by config key sarif.analysers.codeql.enabled
  # Default: False
```

### 12.3 Adapter Design

`codeql.py` implements `AnalyserAdapterBase`.

Adapter stages:

1. Check for existing CodeQL database in the workspace (pre-built by user).
2. If no database exists and `auto_build` is enabled, run `codeql database create`.
3. Run `codeql analyze --format=sarifv2.1.0 --output=<tempfile>`.
4. Parse SARIF output.

### 12.4 CodeQL Predicate ID Extraction

CodeQL results carry predicate information in result properties. Extract:

- `github/alertNumber` if present.
- Rule ID as the query path (e.g., `python/sql-injection`).
- `precision` property for confidence calibration.

### 12.5 CodeQL Tests

Required tests:

- Capability flag defaults to False.
- With flag False, adapter reports unavailable.
- When flag True and CodeQL installed, run produces SARIF for fixture repo.
- CodeQL predicate ID extracted from result properties.
- `precision: very-high` maps to `confidence=parser`.

---

## 13. Optional External SARIF Import Adapters

### 13.1 Purpose

Static analysis results are often produced externally in CI/CD pipelines. The external SARIF import path allows storing and binding results without running the analyser locally.

### 13.2 `external_import.py`

Generic SARIF file import adapter.

```text
ExternalSarifImporter
  import_sarif_file(
    file_path: Path,
    repo_id: str,
    snapshot_id: str,
    analyser_hint: str | None,
  ) -> NormalizedSarifRun
    # Parse the file as SARIF v2.1.0.
    # Normalize alerts and rules.
    # Return NormalizedSarifRun with analyser_id="external" unless hint provided.
```

Rules:

- Import must work even when the local analyser is not installed.
- The raw SARIF file is stored as an artefact.
- External imports must carry provenance noting the import path was external.
- Do not re-run the analyser on import; that would be a separate `run_static_analysis` call.

### 13.3 `sonarqube.py`

SonarQube/SonarCloud SARIF export adapter.

Notes:

- SonarQube exports use standard SARIF v2.1.0 but with SonarQube-specific rule ID formats.
- Rule families must be inferred from SonarQube `tags` property.
- Severity normalization uses SonarQube severity levels: BLOCKER → `critical`, CRITICAL → `high`, MAJOR → `medium`, MINOR → `low`, INFO → `informational`.

### 13.4 GitHub Advanced Security Import

GitHub Advanced Security (GHAS) produces CodeQL SARIF. Import via:

- A locally downloaded SARIF file from the GitHub API.
- Or a SARIF file committed to `.github/codeql` by CI.

The external import adapter handles this; no separate GHAS adapter is needed.

### 13.5 External Import Tests

Required tests:

- External SARIF file import produces valid `NormalizedSarifRun`.
- External import with analyser hint preserves hint as analyser ID.
- Malformed external file produces typed error.
- SonarQube BLOCKER → `critical`.
- GHAS CodeQL SARIF import works through generic importer.

---

## 14. `run_static_analysis` MCP Tool

### 14.1 Purpose

`run_static_analysis` is the MCP tool that executes or imports a static analysis run, stores the normalized results, binds alerts to graph nodes, and emits resource update notifications.

### 14.2 Tool Input

```text
run_static_analysis input
  repo : str                     # Repo ID or path
  analyser : str                 # semgrep, bandit, codeql, external
  ruleset : str | list[str] | None   # Registry ID, file path, or list
  files : list[str] | None       # Specific files; None = all
  snapshot : str | None          # Target snapshot; None = current
  import_sarif_path : str | None # Path to externally-produced SARIF
  config : dict | None           # Analyser-specific config overrides
  task : bool | None             # Whether to run as a task; default auto
```

### 14.3 Tool Output

```text
run_static_analysis output
  run_id : str
  status : str              # completed, failed, task_created
  alert_count : int | None
  rule_count : int | None
  new_critical_high_count : int | None
  delta_from_run_id : str | None
  delta_id : str | None
  sarif_resource_uri : str  # code-intelligence://sarif/{repo}/{run_id}
  run_event_ids : list[str]
  diagnostics : list[str]
```

### 14.4 Tool Behavior

1. Validate repo is registered.
2. Validate analyser is available or SARIF file is provided.
3. Create run record and harness condition reference.
4. Execute analyser or import SARIF file.
5. Normalize output through `SarifNormalizer`.
6. Store `NormalizedSarifRun` in SARIF run store.
7. Store raw SARIF artefact.
8. Bind alerts to graph nodes.
9. Emit `warned_by` graph edges.
10. Compute delta against prior run if one exists.
11. Emit `notifications/resources/updated` for `code-intelligence://sarif/{repo}/{run_id}`.
12. Append operational run events.
13. Return result payload.

### 14.5 Task Support

`run_static_analysis` is task-capable. Long-running analyses (CodeQL database creation, large repo Semgrep run) should use the Phase 4 task infrastructure.

Progress events should include:

- `analyser_started`
- `analysis_complete: N alerts found`
- `normalisation_complete`
- `binding_complete: M alerts bound to symbols`
- `delta_computed`
- `notifications_emitted`

### 14.6 Permission Descriptor

```text
required_mode : execute
path_scope : registered repo root
network_requirement : none (offline mode enforced)
side_effect_class : writes_sarif_store, writes_graph_edges
approval_requirement : not required by default
allowed_stages : S1 and above
```

### 14.7 Tool Tests

Required tests:

- Semgrep run on Python fixture stores alerts.
- Bandit run on Python fixture stores alerts.
- External SARIF import works.
- Alerts are bound to file and symbol nodes.
- `warned_by` edges are present in graph after tool call.
- Delta is computed against prior run.
- `notifications/resources/updated` emitted.
- Task creation for long-running analysis.
- Unregistered repo rejected.
- Unavailable analyser returns typed error.
- Offline mode respected.

---

## 15. `code-intelligence://sarif/{repo}/{run_id}` Resource

### 15.1 Purpose

Exposes normalized SARIF run data for a specific repo and run ID through the MCP resource system.

### 15.2 Resource Payload

```text
SarifRunResource
  run_id : str
  repo_id : str
  snapshot_id : str
  git_sha : str
  analyser_id : str
  analyser_version : str | None
  analyser_name : str
  ruleset_id : str
  ruleset_name : str | None
  invocation_start_ts : str | None
  invocation_successful : bool
  alert_count : int
  rule_count : int
  severity_summary : dict[str, int]
  alerts_by_file : dict[str, list[AlertSummary]]
  rules : list[NormalizedRuleSummary]
  delta_from_run_id : str | None
  delta_summary : SarifDeltaSummary | None
  sarif_artifact_ref : ArtifactRef
  produced_by_run_id : str | None
  schema_version : str
```

### 15.3 Alert Summary In Resource

The resource payload uses `AlertSummary` for compactness rather than full `NormalizedAlert`:

```text
AlertSummary
  alert_id : str
  rule_id : str
  normalized_severity : str
  message : str
  start_line : int | None
  end_line : int | None
  suppressed : bool
  bound_symbol_ids : list[str]
  binding_confidence : str
  baseline_state : str | None
```

### 15.4 Resource Rules

- The resource is subscribable; subscriptions fire after `run_static_analysis` completes.
- Return typed not-found if run_id does not exist.
- Return typed not-found if run_id belongs to a different repo.
- Resource includes `sarif_artifact_ref` so clients can fetch the raw SARIF if needed.
- Large alert lists should be paginated or offer an artefact reference for bulk download.

### 15.5 Resource List Handler

`code-intelligence://repos` already lists registered repos. A query-level SARIF list can be exposed as a flat resource listing:

```text
code-intelligence://sarif/{repo}
  List all run IDs for a repo, ordered by most recent first.
  Payload: list[SarifRunSummary]
```

### 15.6 Subscription Behavior

After `run_static_analysis` completes:

- Emit `notifications/resources/updated` for `code-intelligence://sarif/{repo}/{run_id}`.
- Also emit for any graph resources updated due to new `warned_by` edges (graph slices, summaries).

### 15.7 Resource Tests

Required tests:

- Read SARIF resource for stored run.
- Resource payload includes alert severity summary.
- Subscribable: notification fires after `run_static_analysis`.
- Unknown run_id returns typed not-found.
- Run from different repo rejected.
- SARIF list resource returns ordered run IDs.

---

## 16. SAST Delta Foundation For Downstream Phases

### 16.1 Contract With Phase 11

Phase 11 (patch review) uses SARIF deltas to determine whether a patch introduced new alerts or fixed existing ones.

Phase 6 must provide:

- `compute_sarif_delta(before_run_id, after_run_id) -> SarifDelta`.
- `get_sarif_delta(delta_id) -> SarifDelta`.
- `new_critical_or_high_count` populated in all deltas.
- `appeared_by_severity` and `disappeared_by_severity` breakdown.

Phase 11 rule from the architecture: new critical SARIF alerts appearing after a patch override a `safe` label regardless of the ML classifier.

### 16.2 Contract With Phase 12

Phase 12 (SAST alert repair) uses SARIF deltas to verify that the original alert disappears after applying a patch.

Phase 6 must provide:

- Alert identity via fingerprint so Phase 12 can verify `alert_id in delta.disappeared`.
- Per-alert baseline state tracking so Phase 12 can confirm disappearance.
- Delta comparison against the run that produced the original alert.

### 16.3 Contract With Phase 9

Phase 9 (fault localisation) uses `warned_by` edges as SARIF proximity priors.

Phase 6 must provide:

- `get_alerts_for_file(repo_id, file_path, run_ids)` for file-level proximity.
- `get_alerts_for_symbol(symbol_node_id)` for symbol-level proximity.
- Normalized severity for weighting.

### 16.4 delta_id As First-Class Schema Field

`sarif_delta_id` in the Phase 1 patch/verdict schema must reference a stored `SarifDelta`. Phase 6 must ensure delta records are stable and addressable by ID after storage.

---

## 17. Confidence And Provenance Rules

### 17.1 Evidence Class For SARIF

All SARIF-derived graph facts belong to the `hard static evidence` class when:

- Produced by a deterministic static analyser.
- Alert location resolves unambiguously to a repo-relative file.
- Rule is known, enabled, and not suppressed.

SARIF facts are `structured repository evidence` when:

- Binding is file-only (no symbol overlap).
- The analyser is unknown or external.
- The alert was suppressed.
- The snapshot used for the SARIF run differs from the current graph snapshot.

### 17.2 Confidence Levels Per Binding Type

- Alert bound to symbol with full containment: `confidence=parser`.
- Alert bound to symbol with partial overlap: `confidence=heuristic`.
- Alert bound to file only: `confidence=heuristic`.
- Alert with unresolvable file path: `confidence=none`, treated as unbound.
- Mixed-snapshot binding: one step lower than the normal confidence.

### 17.3 Provenance Fields

Every `sast_rule` and `sarif_alert` node must carry:

- `repo_id`
- `git_sha` or `worktree_snapshot_id`
- `analyser_id`
- `analyser_version`
- `run_id`
- `confidence`
- `derivation` = `analyser`

`warned_by` edges additionally carry:

- `rule_id`
- `alert_id`
- `binding_type`
- `run_id`
- `snapshot_id`

### 17.4 Staleness

A `warned_by` edge is stale when:

- The graph snapshot has advanced past the SARIF run's snapshot.
- The file containing the alert has been modified since the SARIF run.

Stale `warned_by` edges must not be presented as current evidence. The graph store should mark them with a `stale_since_snapshot_id` field. Downstream queries should respect the staleness flag.

---

## 18. Security, Privacy, And Redaction

### 18.1 Alert Content Privacy

Alerts may contain excerpts of source code or internal filenames. Phase 6 must apply the same redaction policy as operational events.

Rules:

- Do not expose absolute host paths in stored alert records.
- Apply the workspace redaction policy to alert message text when logging.
- Alert code snippets embedded in SARIF must be stored in the artefact, not inline in log events.

### 18.2 False Positive Disclosure

Suppressed alerts are retained in the store with suppression metadata. They are not deleted. Suppression justifications may contain developer-sensitive rationale.

Rules:

- Suppression justification text is redacted from log events.
- Suppression justification is stored in the raw SARIF artefact and the `sarif_alerts` table with a redaction flag when warranted.

### 18.3 External SARIF Import Trust

External SARIF files come from outside the tool's control.

Rules:

- Validate SARIF schema before ingesting.
- Treat alert messages as untrusted text: check for injection patterns before storing.
- Do not execute fix proposals in SARIF `fixes` arrays; they are stored as evidence only.
- Record the import source path in provenance.

### 18.4 Tool Execution Safety

Rules:

- Semgrep and Bandit subprocess execution must use `asyncio.create_subprocess_exec` with explicit argument lists (no `shell=True`). See tech stack §13 and §15 — `subprocess.run` blocks the asyncio event loop and must not be used in async code paths.
- No arguments from user input should be interpolated into subprocess command strings without validation.
- Analyser output is treated as untrusted: parse with explicit schema, not `eval`.
- Temporary files for SARIF output must be created in the workspace tmp directory and deleted after ingestion.

---

## 19. Test Plan

### 19.1 Parser Tests

Required:

- Valid SARIF v2.1.0 parses.
- Version mismatch raises typed error.
- Malformed JSON raises typed error.
- URI resolution handles `uriBaseId`.
- Large SARIF file parses without OOM.

### 19.2 Normalizer Tests

Required:

- Severity mapping per tool.
- CVSS-based severity override.
- CWE extraction in multiple formats.
- Rule family inference from CWE and rule ID.
- Predicate ID extraction per tool format.

### 19.3 Store Tests

Required:

- Store, retrieve, list, and delete SARIF runs.
- Alert query by file.
- Alert query by symbol.
- Alert query by severity.
- Latest run query.

### 19.4 Fingerprint Tests

Required:

- Stable fingerprint under whitespace change.
- Different fingerprint on rule ID change.
- SARIF-provided fingerprint preserved.

### 19.5 Binding Tests

Required:

- File binding on exact path.
- Symbol binding with full containment.
- Symbol binding with partial overlap.
- File-only binding when no symbol overlaps.
- Unresolvable path: diagnostic only.
- Mixed-snapshot flagged.

### 19.6 `warned_by` Edge Tests

Required:

- Primary `warned_by` edge emitted.
- Secondary `warned_by` edge for multiple overlapping symbols.
- Suppressed alert bound with suppression tag.
- Edge round-trips through Phase 1 schema.

### 19.7 Delta Tests

Required:

- Zero-diff on identical runs.
- Appeared, disappeared, unchanged, changed categories all exercised.
- `new_critical_high_count` correct.
- Delta persisted and retrievable.

### 19.8 Adapter Tests

Required:

- Semgrep: availability, run, offline mode, timeout.
- Bandit: availability, run, SARIF fallback.
- CodeQL: capability flag off by default.
- External import: valid file, malformed file, analyser hint.
- SonarQube: BLOCKER normalization.

### 19.9 MCP Tool Tests

Required:

- `run_static_analysis` stores run and alerts.
- Delta computed and stored.
- `warned_by` edges in graph.
- Notifications emitted.
- Task creation for long-running run.
- Unregistered repo rejected.
- Offline mode respected.

### 19.10 Resource Tests

Required:

- SARIF resource returned for stored run.
- SARIF list resource.
- Notification on run completion.
- Unknown run_id: typed not-found.

### 19.11 Regression Tests

Required:

- `run_static_analysis` tool descriptor snapshot.
- SARIF resource descriptor snapshot.
- Severity normalization snapshot per tool.
- Rule family mapping snapshot.

---

## 20. Work Packages

### P6.1 SARIF Data Models, Parser, And Normalizer

Build:

- SARIF v2.1.0 data models.
- Parser with URI resolution.
- Severity normalizer.
- Rule-family normalizer.
- CWE and predicate ID extractor.

Deliverables:

- `sarif/models.py`
- `sarif/parser.py`
- `sarif/normalizer.py`
- Parser and normalizer tests.
- SARIF fixture files.

Acceptance:

- All fixture SARIF files parse and normalize without error.

### P6.2 SARIF Run Store

Build:

- `NormalizedSarifRun`, `NormalizedRule`, `NormalizedAlert` models.
- SQLite schema migration.
- `SarifRunStore` query interface.

Deliverables:

- `sarif/store.py`
- Phase 2 schema migration.
- Store tests.

Acceptance:

- Store, retrieve, and query SARIF runs.

### P6.3 Alert Fingerprinting

Build:

- Fingerprint computation.
- Stability guarantees.
- SARIF fingerprint preservation.

Deliverables:

- `sarif/fingerprint.py`
- Fingerprint tests.

Acceptance:

- Fingerprint stable under whitespace change, different on content change.

### P6.4 Alert-To-Graph Binding And `warned_by` Edges

Build:

- File binding.
- Symbol binding with span overlap.
- `warned_by` edge emitter.
- `sast_rule` and `sarif_alert` node builders.

Deliverables:

- `sarif/binding.py`
- `sarif/warned_by.py`
- Binding and edge tests.

Acceptance:

- Alerts from fixture SARIF bound to fixture graph nodes. `warned_by` edges in graph.

### P6.5 SARIF Delta Utility

Build:

- Alert matching algorithm.
- `SarifDelta` model.
- Delta persistence.
- `SarifDeltaSummary`.

Deliverables:

- `sarif/delta.py`
- Delta tests.

Acceptance:

- Delta correctly classifies appeared/disappeared/unchanged/changed for before/after fixtures.

### P6.6 Semgrep Adapter

Build:

- `SemgrepAdapter`.
- Ruleset resolution and hashing.
- Subprocess execution.
- Offline enforcement.
- Timeout handling.

Deliverables:

- `sarif/adapters/semgrep.py`
- `sarif/adapters/ruleset.py`
- Semgrep adapter tests.

Acceptance:

- Semgrep run on Python fixture produces stored alerts.

### P6.7 Bandit Adapter

Build:

- `BanditAdapter`.
- SARIF native mode.
- JSON fallback and synthetic SARIF converter.

Deliverables:

- `sarif/adapters/bandit.py`
- Bandit adapter tests.

Acceptance:

- Bandit run on Python fixture produces stored alerts.

### P6.8 Optional CodeQL Adapter And External Import

Build:

- `CodeQLAdapter` behind capability flag.
- `ExternalSarifImporter`.
- `SonarQubeAdapter`.

Deliverables:

- `sarif/adapters/codeql.py`
- `sarif/adapters/external_import.py`
- `sarif/adapters/sonarqube.py`
- Adapter tests.

Acceptance:

- CodeQL flag defaults to False.
- External import works for fixture SARIF files.

### P6.9 `run_static_analysis` MCP Tool

Build:

- Tool handler.
- Orchestration of run/import/normalize/store/bind/delta/notify pipeline.
- Task support.
- Permission descriptor.
- Telemetry.

Deliverables:

- `mcp_server/tools/sarif.py`
- Tool tests.

Acceptance:

- `run_static_analysis` stores run, binds alerts, and emits notifications.

### P6.10 SARIF Resource Handler And Regression Tests

Build:

- `code-intelligence://sarif/{repo}/{run_id}` resource handler.
- `code-intelligence://sarif/{repo}` list resource.
- Subscription integration.
- Tool descriptor and resource descriptor regression tests.

Deliverables:

- `mcp_server/resources/sarif.py`
- Resource and regression tests.

Acceptance:

- MCP client can read SARIF resource and receive update notification.

---

## 21. Suggested Implementation Order

Recommended order:

1. SARIF data models and parser.
2. Severity and rule-family normalizer.
3. SARIF fixture files.
4. SARIF run store schema and query interface.
5. Alert fingerprinting.
6. Alert-to-graph binding (file binding first).
7. Alert-to-symbol binding.
8. `warned_by` edge emitter.
9. SARIF delta utility.
10. Semgrep adapter.
11. Bandit adapter.
12. `run_static_analysis` tool (Semgrep + Bandit path).
13. SARIF resource handler.
14. Resource subscriptions and notifications.
15. Optional CodeQL adapter.
16. External SARIF import adapter.
17. SonarQube adapter.
18. Phase 5 `warned_by` back-population for Pyright/clangd nodes.
19. Regression test harness.

Reasoning:

- Parser and store land before any adapter to establish the ingest pipeline.
- Fingerprinting lands before the delta utility.
- File binding before symbol binding, since file binding is required for symbol binding.
- Semgrep lands before Bandit because it covers more languages and has SARIF native support.
- CodeQL is last among adapters because it requires database build infrastructure.

---

## 22. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 6 |
|---|---|
| Phase 7 - Interface plugins | `warned_by` edges on interface boundary symbols; SARIF alerts on IDL or route handler nodes |
| Phase 8 - Repo-QA | SARIF alert evidence for "is this symbol flagged?" behaviour questions |
| Phase 9 - Fault localisation | `get_alerts_for_file` and `get_alerts_for_symbol` as SARIF proximity priors; `warned_by` edge traversal |
| Phase 10 - Evaluation harness | SARIF run store for eval SAST delta metrics; alert count as a run metric |
| Phase 11 - Patch review | `compute_sarif_delta` and `SarifDelta` for appeared/disappeared alerts; `new_critical_or_high_count` as hard override signal; `sarif_delta_id` in verdict schema |
| Phase 12 - SAST repair | Alert fingerprint for disappearance verification; `get_alerts_for_symbol` to select repair targets; `run_static_analysis` to re-run after patch |
| Phase 13 - Bug-resolve | SARIF alert nodes as investigation context; `warned_by` edges in graph neighbor traversal |
| Phase 14 - Implementation-check | SARIF alerts as evidence for static-verdict computation; generated Semgrep/CodeQL predicates produce new `sast_rule` nodes |
| Phase 15 - Blast radius | SARIF reachability facts for static analysis impact groups |
| Phase 17 - Memory | SARIF deltas stored in trajectory records; `sarif_delta` field in trajectory schema |
| Phase 18 - Release gates | PoC+ SARIF delta validation; SAST alert repair metrics in T3/T4 |

---

## 23. Exit Criteria Mapping

Source Phase 6 exit criterion:

- `run_static_analysis(repo, ruleset)` stores normalized SARIF.

Concrete acceptance:

- `run_static_analysis` with Semgrep adapter on Python fixture stores `NormalizedSarifRun` in SARIF store.
- `run_static_analysis` with Bandit adapter on Python fixture stores `NormalizedSarifRun`.
- External SARIF import stores `NormalizedSarifRun`.
- Stored run is retrievable by `run_id`.

Source Phase 6 exit criterion:

- Alerts are linked to graph nodes where possible.

Concrete acceptance:

- Alerts in fixture SARIF run have `bound_file_node_id` set.
- Alerts spanning function bodies have `bound_symbol_node_ids` set.
- `warned_by` edges present in graph store for bound alerts.
- Unresolvable alert paths produce typed diagnostic.

Source Phase 6 exit criterion:

- External SARIF import preserves analyser name, rule ID, predicate ID where available, severity, locations, and provenance.

Concrete acceptance:

- External import of `external_generic.sarif.json` fixture: all alerts have `rule_id`, `analyser_name`, `normalized_severity`, `file_path`, `start_line`.
- Predicate ID from CodeQL fixture preserved in `NormalizedRule.predicate_id`.
- Raw SARIF stored as artefact with hash.

Source Phase 6 exit criterion:

- SARIF delta can identify appeared, disappeared, and changed alerts.

Concrete acceptance:

- `compute_sarif_delta(before_run_id, after_run_id)` for `delta_before.sarif.json` and `delta_after.sarif.json` fixtures correctly classifies appeared, disappeared, unchanged, and changed alerts.
- `new_critical_or_high_count` is correct.
- Delta is persisted and retrievable by `delta_id`.

---

## 24. Definition Of Done

Phase 6 is done when:

- SARIF v2.1.0 data models and parser are implemented and tested.
- Severity and rule-family normalizer covers Semgrep, Bandit, CodeQL, and generic external tools.
- SARIF run store stores, retrieves, and queries normalized runs and alerts.
- Alert fingerprinting is stable under whitespace and positional noise.
- File and symbol binding produce `bound_file_node_id` and `bound_symbol_node_ids` for fixture alerts.
- `warned_by` graph edges are emitted for all bound alerts.
- Semgrep adapter runs and ingests results for Python fixture repo.
- Bandit adapter runs and ingests results for Python fixture repo.
- Optional CodeQL adapter is gated by `CODEQL_BACKEND_ENABLED=False`.
- External SARIF import works for the generic fixture file.
- SARIF delta utility classifies appeared/disappeared/unchanged/changed correctly.
- `run_static_analysis` MCP tool is task-capable and stores results, binds alerts, and emits notifications.
- `code-intelligence://sarif/{repo}/{run_id}` resource returns normalized run payload.
- SARIF resource subscriptions fire after `run_static_analysis` completes.
- All Phase 5 Python graph tests continue to pass.
- SARIF evidence is kept separate from verdicts throughout.

---

## 25. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Semgrep download rules at runtime breaks HC5 network policy | HC5 violation in CI or restricted environments | Pre-fetch rules to workspace; enforce `--offline` flag or equivalent; test with network mocked off |
| Bandit SARIF output not available in older installed versions | Bandit adapter silently produces no alerts | Detect version before choosing SARIF vs JSON mode; test both paths; synthetic SARIF converter as fallback |
| Alert fingerprint collisions | Different alerts share same ID; delta corruption | Use 16-char SHA-256 prefix; test collision rate on fixtures; store full fingerprint in artefact |
| Symbol binding is too broad for multi-line alert regions | Wrong `warned_by` edges pollute the graph | Prefer full-containment binding; mark partial-overlap as `heuristic`; expose binding type in all edges |
| SARIF `uriBaseId` resolution fails for complex project layouts | All alerts marked unresolvable | Document supported `uriBaseId` patterns; test with SRCROOT and repo-relative patterns; emit diagnostic with actionable message |
| CodeQL database creation mutates repository build artifacts | Unexpected side effects for users | Default flag False; require explicit opt-in; warn before running `auto_build`; document that it runs compiler |
| External SARIF import from adversarial source injects data | Graph poisoning via crafted alert messages | Schema-validate before ingesting; treat message text as untrusted; no code execution from `fixes` arrays |
| SARIF delta matching is too strict for fuzzy-line repos | False appeared/disappeared count misleads patch review | Implement ±5 line fuzzy rule-and-file match for `changed/location_shifted`; validate on before/after fixture |
| Phase 5 back-population of `warned_by` for Pyright/clangd nodes is slow | Migration blocks first startup | Run as async background task, not on every startup; track migration status in workspace metadata |
| `run_static_analysis` task timeout exceeds budget | Task hangs, run record stuck in running state | Budget manager timeout integration; task runner kills subprocess after budget hard stop; checkpoint partial results |

---

## 26. Completion Report Template And Minimal First Slice

### 26.1 Completion Report Template

When Phase 6 implementation is complete, report:

```text
Phase 6 completion report

Implemented:
- SARIF v2.1.0 parser:
- Severity and rule-family normalizer:
- SARIF run store:
- Alert fingerprinting:
- File and symbol binding:
- warned_by edge emitter:
- Semgrep adapter:
- Bandit adapter:
- Optional CodeQL adapter (capability flag):
- External SARIF import:
- SonarQube adapter:
- SARIF delta utility:
- run_static_analysis MCP tool:
- SARIF resource handler:
- Subscription integration:
- Phase 5 warned_by back-population:

Verification:
- Parser tests:
- Normalizer tests:
- Store tests:
- Binding tests:
- warned_by edge tests:
- Delta tests:
- Semgrep adapter tests:
- Bandit adapter tests:
- External import tests:
- MCP tool tests:
- Resource tests:
- Regression harness:
- Local verify command:

Exit criteria:
- run_static_analysis stores normalized SARIF:
- Alerts linked to graph nodes:
- External SARIF import preserves provenance:
- SARIF delta classifies appeared/disappeared/changed:
- Phase 5 Python graph tests still pass:

Known limitations:
-

Follow-up for Phase 7 (interface plugins):
-
```

### 26.2 Minimal First Slice Within Phase 6

If Phase 6 needs to be split further, implement this first:

1. SARIF v2.1.0 data models and parser.
2. Severity and rule-family normalizer.
3. SARIF fixture files (Semgrep and external).
4. SARIF run store with SQLite schema.
5. Alert fingerprinting.
6. File binding only (no symbol binding yet).
7. `warned_by` edges for file-level bindings.
8. Semgrep adapter.
9. `run_static_analysis` tool with Semgrep path.
10. `code-intelligence://sarif/{repo}/{run_id}` resource.
11. Subscription notification for SARIF resource.

This minimal slice establishes the ingest pipeline, stores Semgrep results, and wires `warned_by` edges to file nodes. Symbol binding, the delta utility, Bandit, and optional adapters follow in subsequent slices.
