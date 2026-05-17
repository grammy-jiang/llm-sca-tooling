# LLM-SCA Tooling Implementation Specification

This specification defines the named architectural surface and exit criteria
that the implementation must satisfy. Sources:
`docs/llm-sca-tooling-architecture.md` §2.1 and
`docs/llm-sca-tooling-implementation-plan.md` §2.1 and §3 (per-phase exit criteria).

## 1. Named MCP Resources

The implementation must register the following MCP resources:

- `code-intelligence://repos` exposes registered repositories.
- `code-intelligence://schema/graph.schema.json` exposes the graph schema.
- `code-intelligence://schema/run-record.schema.json` exposes the run record schema.
- `code-intelligence://graph/{repo}` exposes the graph manifest with chunk references.
- `code-intelligence://graph/slice/{repo}/{files}` exposes graph slices for files.
- `code-intelligence://summary/{repo}/{symbol_path}` exposes lazy symbol summaries.
- `code-intelligence://blame/{repo}/{file_path}` exposes git blame chains.
- `code-intelligence://build-evidence/{repo}` exposes build and test evidence.
- `code-intelligence://sarif/{repo}/{run_id}` exposes SARIF run results.
- `code-intelligence://eval/{run_id}` exposes evaluation runs.
- `code-intelligence://memory/{repo}/trajectories` exposes stored trajectories.
- `code-intelligence://interfaces` lists interface plugin records.
- `code-intelligence://interfaces/{plugin_id}/{interface_name}` exposes interface records.
- `code-intelligence://runs/{run_id}` exposes run records.
- `code-intelligence://runs/{run_id}/harness-condition` exposes Harness Condition Sheets.
- `code-intelligence://operations/{repo}/ledger` exposes the operational ledger.
- `code-intelligence://governance/{repo}/policy` exposes effective governance policy.
- `code-intelligence://governance/{repo}/manifest-state` exposes manifest state.
- `code-intelligence://readiness/{repo}` exposes readiness reports.
- `code-intelligence://incidents/{incident_id}` exposes incident records.

## 2. Named MCP Tools

The implementation must register the following MCP tools.

### 2.1 Query and evidence tools

- `find_callers` returns callers for a symbol.
- `find_callees` returns callees for a symbol.
- `get_relevant_files` ranks files relevant to an issue.
- `get_graph_slice` returns a graph slice for files.
- `trace_cross_language` traverses interface boundaries.
- `git_blame_chain` returns blame entries with parent commits.
- `get_interface_contract` returns the interface contract for a symbol.
- `classify_repo_question` classifies a repository question.
- `answer_repo_question` answers a classified question with evidence.
- `run_static_analysis` runs or imports SARIF and binds to graph nodes.
- `get_predicate_examples` retrieves predicate examples for SAST repair.
- `retrieve_memory` returns memory hints for an issue.

### 2.2 Analysis and verification tools

- `classify_patch_risk` classifies a diff into risk classes.
- `run_sast_repair` proposes a patch for a SARIF alert.
- `compute_rds_features` computes RDS v0.2 feature vectors.
- `record_eval_result` records an evaluation result.
- `record_trajectory` records a workflow trajectory.
- `evolve_static_rules` is an optional offline rule-refinement workflow.

### 2.3 Operational harness tools

- `record_run_event` appends a run event to a run record.
- `record_harness_condition` captures a Harness Condition Sheet.
- `evaluate_tool_policy` returns allow/deny/approval-required decisions.
- `detect_run_anomalies` flags doom-loops and budget overruns.
- `compare_run_traces` compares run traces.
- `assess_harness_stage` returns the current S0..S3 stage.
- `classify_harness_drift` classifies artefacts as missing/stale/relaxed/out-of-stage/clean.
- `validate_harness_controls` runs non-relaxation and readiness checks.
- `compute_readiness_score` returns the five-axis readiness score.
- `run_maintainability_oracles` runs structural maintainability oracles.
- `run_prompt_manifest_regression` runs manifest and tool-description regression tests.
- `promote_operational_lesson` promotes a reviewed lesson.
- `record_incident` opens an incident record.

### 2.4 Build and update tools

- `graph_build` builds the repository graph as a task.
- `graph_update` updates the graph for changed files.
- `register_repo` registers a repository.
- `plugin_reload` reloads an interface plugin.
- `memory_compact` compacts trajectory memory deterministically.

### 2.5 Workflow launchers

- `run_implementation_check` runs the seven-stage implementation-check DAG.
- `run_issue_resolution` runs the bug-resolve workflow.
- `run_patch_review` runs the patch-review workflow.
- `run_eval_suite` runs T1..T4 evaluation suites.
- `run_operational_review` runs the operational review workflow.
- `run_readiness_audit` runs the readiness audit workflow.

### 2.6 Live evidence tool

- `capture_trace` captures a scoped dynamic trace.

## 3. Public MCP prompts

The implementation must register the following public prompts:

- `implementation-check`
- `bug-resolve`
- `patch-review`
- `operational-review`
- `readiness-audit`

## 4. Private skill templates

The implementation must register the following private workflow templates:

- `investigate`
- `repair`
- `audit`
- `blast-radius`
- `sast-repair`
- `risk-classify`
- `evaluate`

## 5. Protocol behaviour requirements

- `resources/subscribe` and `notifications/resources/updated` notifications fire
  for graph, summary, SARIF, interface, eval, memory, run, readiness,
  governance, and incident resources.
- `notifications/resources/list_changed` fires when repos or interface plugins
  are registered or removed.
- Task-capable tools use task descriptors, `CreateTaskResult`/`taskId`
  handling, persistence, `tasks/get`, `tasks/result`, optional `tasks/list`,
  `tasks/cancel`, progress and `notifications/tasks/status`, TTL, restart
  recovery, high-entropy task IDs, and authorization binding.
- Optional MCP Sampling capability negotiation is supported for review
  subagents; when unsupported the workflow falls back to a local interface.

## 6. Hard constraints

- `HC1`: No plaintext secrets in repository files, prompts, logs, or commits.
  `detect-secrets` pre-commit hook and `.secrets.baseline` are required.
- `HC2`: No agent-authored writes outside the path allowlist.
- `HC3`: Destructive commands require explicit human approval before execution.
- `HC4`: Database migrations and irreversible infrastructure changes are
  authored but never executed autonomously.
- `HC5`: Network egress is denied by default; only explicitly listed
  destinations are accessed.
- `HC6`: Red-class data must never enter prompts, tool arguments, trace logs,
  plan files, or stored artefacts.

## 7. Phase exit criteria

### 7.1 Phase H0 — Harness Quality Foundation

- Every implementation phase declares its Harness Condition Sheet.
- Every workflow-producing phase has a session trace and verification record.
- A parseable run-record schema exists before workflow implementation begins.
- A local `verify` path exists and is documented.
- Manifest and tool-description changes have tests or documented review
  criteria.
- Operational review and incident templates are available for failed runs.
- Harness drift checks reject relaxed policy changes such as disabling secrets
  scans or bypassing permissions.
- AI-readiness reports are comparable over time and fail the release gate when
  a readiness axis regresses without an accepted waiver.

### 7.2 Phase 0 — Python Package Skeleton

- The package installs locally.
- The test suite runs.
- The local verify command runs the same core checks expected before merge.
- The CLI prints version and config.
- An empty MCP server starts in development mode.
- The plugin registry loads a no-op plugin.
- A dummy run can create a run record, append an event, and close with a status.

### 7.3 Phase 1 — Shared Schemas and Evidence Model

- All schema objects round-trip through JSON.
- Invalid graph edges and missing provenance fail validation.
- Every graph fact carries `repo`, `git_sha`, optional `worktree_snapshot_id`,
  `file`, `span`, `confidence`, and `derivation`.
- Operational events are append-only, sequence-numbered, and redaction-aware.
- Incidents and promotion candidates reference source run/event IDs.

### 7.4 Phase 2 — Local Graph Store and Repository Registry

- `register_repo` stores repository metadata.
- Graph facts can be added and queried.
- Dirty worktree snapshots are represented.
- Mixed-snapshot queries are detectable.
- Run records can be queried by repo, workflow, status, incident type, and time.

### 7.5 Phase 3 — Repository Indexing MVP

- `graph_build(repo_path)` indexes a small Python repo.
- `graph_update(repo_path)` updates changed files without rebuilding everything.
- Graph slices include files, symbols, imports, tests, and provenance.
- Symbol summaries and blame chains can be cached, invalidated, and retrieved
  with snapshot provenance.
- Stale index state is visible.

### 7.6 Phase 4 — MCP Server Core

- An MCP client can list resources and call graph tools.
- Long-running `graph_build` can run as a task.
- Resource subscriptions and update/list-changed notifications fire for graph,
  summary, repo, and plugin changes.
- MCP tools expose permission metadata and produce trace events.
- Task IDs are high-entropy, TTL-bound, and recoverable after server restart.

### 7.7 Phase 4A — Operational Harness Runtime Plane

- A workflow task creates a run, appends events, and closes with a final
  status.
- `run_operational_review(run_id)` returns `process-compliant`,
  `process-noncompliant`, `trace-incomplete`, `budget-exhausted`, or
  `needs-readiness-work` with evidence.
- `run_readiness_audit(repo)` returns a score and concrete missing controls.
- `assess_harness_stage(repo)` returns a stage and next-stage controls.
- `classify_harness_drift(repo)` blocks `relaxed` drift.
- `validate_harness_controls(repo)` runs manifest non-relaxation, readiness
  no-regression, and prompt regression checks.

### 7.8 Phase 5 — Language Backend Expansion

- Python, JS/TS, and C/C++ repositories produce symbols and imports.
- At least one call graph backend works per target language.
- Backend errors are captured as index diagnostics.

### 7.9 Phase 6 — SARIF and Static Analysis Layer

- `run_static_analysis(repo, ruleset)` stores normalized SARIF.
- Alerts are linked to graph nodes where possible.
- External SARIF import preserves analyser name, rule ID, severity, locations,
  and provenance.
- SARIF delta identifies appeared, disappeared, and changed alerts.

### 7.10 Phase 7 — Cross-Language Interface Plugin System

- `trace_cross_language(start_symbol)` crosses at least one plugin boundary.
- Interface contracts are available as resources.
- Cross-repo traversal works when two registered repos are linked by an
  interface.

### 7.11 Phase 8 — Repository Query and Repo-QA MVP

- File-location questions return cited files and symbols.
- Behaviour-trace questions return graph paths or `unknown`.
- Answers lacking graph/code evidence cannot be marked high confidence.

### 7.12 Phase 9 — Fault Localisation

- `get_relevant_files(issue_text)` returns ranked files with evidence.
- The `investigate` template returns suspect symbols and files with reasoning
  and uncertainty.
- Low agreement between semantic retrieval and graph/static evidence produces
  an uncertain localisation.

### 7.13 Phase 10 — Evaluation Harness Baseline

- A smoke eval run produces stored metrics.
- Every eval run records a Harness Condition Sheet.
- RDS features are computed and saved per instance.
- Eval reports are reproducible from stored artefacts.
- Eval reports include operational metrics beside task metrics.
- Manifest/tool-description regression cases can fail independently.

### 7.14 Phase 11 — Patch Review and Risk Gates

- `run_patch_review(diff)` returns per-axis findings, evidence, uncertainty,
  and recommendation.
- New critical SARIF alerts, broken contracts, and failing required tests
  override a `safe` label.
- Out-of-scope writes, unapproved tool use, or missing telemetry override a
  `safe` label.
- Trace-incomplete, budget-exhausted, or process-noncompliant runs cannot
  receive an auto-merge recommendation.
- Structural maintainability failures block merge even when tests pass.
- `unknown` is returned when classifier calibration is missing.

### 7.15 Phase 12 — Static-Analysis Alert Repair

- `run_sast_repair(alert_id)` proposes a patch for a known alert fixture.
- The original alert must disappear before the alert is considered fixed.
- New higher-severity alerts block success.
- Confirmed false positives can produce a reviewed suppression but not an
  unreviewed analyser-rule mutation.

### 7.16 Phase 13 — Bug-Resolve Workflow

- `run_issue_resolution(issue_text)` produces ranked suspects, patch
  candidate, certificate, gate results, patch-risk verdict, blast-radius map,
  Harness Condition Sheet, and run record reference.
- Failed or uncertain gates produce a non-merge recommendation.
- Process-noncompliant, trace-incomplete, or budget-exhausted runs cannot
  recommend merge.

### 7.17 Phase 14 — Implementation-Check Workflow

- `run_implementation_check(spec)` returns clause-level `satisfied`,
  `violated`, or `unknown`.
- Ungrounded clauses are preserved as `unknown`, not dropped.
- Hard predicate failures dominate soft positive evidence.
- The stage-7 aggregator preserves calibrated confidence and ECE bucket per
  clause.
- Implementation-check reports include run record, harness condition, and
  operational compliance status.

### 7.18 Phase 15 — Blast Radius

- Given a diff, the tool reports local, test, interface, cross-repo, SAST, and
  documentation impact.
- Ambiguous links are separated from confirmed links.
- Generated files and ABI-sensitive C/C++ changes receive explicit impact
  notes.

### 7.19 Phase 16 — Dynamic Trace Augmentation

- `capture_trace(script, scope_filter)` stores raw trace and returns
  compressed evidence.
- Non-reproducing traces are represented as uncertainty rather than hard
  disproof.

### 7.20 Phase 17 — Trajectory Memory and Experience Replay

- Workflows record trajectories.
- `retrieve_memory(issue_text, phase)` returns useful hints plus
  rejected-memory notes.
- `memory_compact` compacts memory deterministically.
- Unreviewed operational lessons remain run artefacts and are not retrieved as
  durable memory.

### 7.21 Phase 18 — Full Evaluation, Calibration, and Release Gates

- T1..T4 run metadata is stored as eval resources.
- Release reports include Harness Condition Sheets and AI-readiness scores.
- Release reports include process-compliance rate, trace replay success rate,
  policy violations, budget hard stops, incident recidivism, and cost per
  accepted verdict.
- Release gates are reproducible from stored artefacts.

### 7.22 Phase 19 — Operational Hardening and Distribution

- The tool installs as a Python package.
- The local MCP server indexes and serves a multi-repo workspace.
- Documentation explains limitations, confidence behaviour, and release gates.
- A production release can be diagnosed from stored traces, eval artefacts,
  and manifest/tool versions.
- Re-running the harness check is idempotent when no drift exists.
