# LLM-SCA Tooling Implementation Plan

> Date: 2026-05-09
> Source architecture: `llm-sca-tooling-architecture.md`
> Goal: Convert the architecture's feature/function design into dependency-aware implementation phases for a Python application/package.
> Citation policy: Paper anchors are inherited from `llm-sca-tooling-architecture.md` §6 and §6.1. This plan keeps anchors beside the implementation work they justify; the source architecture remains the full citation registry.
> Harness-engineering sources: `/home/grammy-jiang/Documents/Research/harness-engineering/harness-engineering-for-local-coding-agents-research-report.md` and `/home/grammy-jiang/Documents/Research/harness-engineering/harness-engineering-for-local-coding-agents-engineering-guide.md`.
> Harness objective: make the final application correct, observable, governable, cost-bounded, safe, reviewable, and continuously improvable under real local-agent workflows.

---

## 1. Planning Principles

The architecture separates the product into five major surfaces:

1. `code-intelligence` MCP server
2. `code-audit` workflow skill/orchestrator
3. Evaluation harness
4. Operational harness plane: run records, harness-condition sheets, permission/tool policy, budgets, monitors, incidents, harness stage/drift classification, readiness audit, operational review, and reviewed lesson promotion
5. Operational guardrails: SARIF, RDS logging, memory retention, calibration, provenance, and trace/redaction policy

The implementation order should follow the evidence hierarchy in the architecture:

1. Build deterministic Python evidence collection first.
2. Put all graph, SARIF, snapshot, task, and verdict data behind typed schemas.
3. Add LLM or ML components only behind auditable interfaces.
4. Treat LLM output as a hypothesis until checked by graph, static analysis, tests, traces, contracts, or calibrated model evidence.
5. Preserve `unknown` as a valid verdict whenever evidence is stale, missing, ambiguous, or uncalibrated.
6. Treat the application harness as part of the product, not only as development scaffolding: policies, permissions, telemetry, verification, memory, and evaluation must be versioned and testable.
7. Use the harness-quality formula from the local-agent guide:
   `good output = correct behaviour + maintainable structure + policy compliance + traceable process`.

The central dependency is:

```text
Typed evidence model
  -> repository graph and index
  -> MCP resources/tools/tasks
  -> operational run records, policy, budgets, and monitors
  -> SARIF and interface plugins
  -> localisation and repo-QA
  -> patch review and gates
  -> repair workflows
  -> implementation-check
  -> dynamic traces and memory
  -> production release gates
```

Citation traceability is part of the implementation work. Any issue, ADR, design note, benchmark report, or non-trivial implementation PR derived from a paper-backed method should carry the same paper anchors used below. End-user workflow output should still focus on evidence, verdict, risk, and next action rather than exposing paper machinery by default.

### 1.1 Harness Quality Spine

Harness engineering adds a cross-cutting quality spine to every phase. A phase is not complete when the code compiles; it is complete when the feature can be operated, audited, bounded, and evaluated under the same conditions expected from the final tool.

| Harness control | Implementation meaning for this tool | Required artefacts | Blocks release when missing |
|---|---|---|---|
| H0 - Supply-chain trust | Tool binaries, MCP servers, language backends, prompt assets, and dependencies are pinned or provenance-tracked before their output is trusted. | Lockfiles, dependency scan output, MCP/tool inventory, analyser version records | Yes |
| H1 - Live observability | Long-running workflows emit structured traces while they run, not reconstructed summaries after failure. | Session JSONL or equivalent, task events, tool calls, costs, context decisions, diffs, approvals | Yes |
| H2 - Manifest control plane | Project and product policy lives in versioned manifests rather than implicit prompts. | `AGENTS.md`, runtime overlays (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`), selected `SKILL.md` templates, `.agent/plan.md`, MCP tool descriptions | Yes |
| H3 - Context and cost budgets | Context assembly, compaction, retrieval, tokens, wall-clock time, and command budgets are explicit and measured. | Budget schema, context-policy fields, compaction events, cost metrics | Yes for workflow release |
| H4 - Permissions and sandbox | Read, search, edit, execute, network, and commit capabilities are separated by mode and path scope. | Tool DAG, permission profiles, path allowlists, sandbox policy | Yes |
| H5 - Verify-before-commit | Model proposals are accepted only after deterministic or independent checks pass. | Format/lint, tests, SAST, secrets, dependency scans, invariant checks, DryRUN predictions | Yes |
| H6 - Maintainability oracles | A patch can fail even when tests pass if it violates structure, dependency, ownership, or side-effect boundaries. | Architecture checks, dependency rules, structural review criteria, hidden maintainability probes | Yes for patch-producing workflows |
| H7 - Evaluation harness | Quality claims hold the model/runtime fixed and report the harness condition. | Harness Condition Sheet, T1-T4 runs, reliability surface, repeated trials, flaky-test filtering | Yes |
| H8 - Diagnosis and rollback | Failed runs can be replayed, compared, quarantined, and rolled back. | Trace links, artefact manifests, incident template, recovery command/docs | Yes for production release |
| H9 - Governed memory | Durable memory is schema-grounded, provenance-linked, reviewable, and never overrides current hard evidence. | Memory schemas, write gates, redaction, utility scores, eviction policy | Yes before memory defaults on |
| H10 - Governed harness evolution | Changes to manifests, prompts, tools, gates, and skills are tested like product code. | Manifest regression tests, semantic mutation cases, compatibility checks, rollback plan | Yes for release gate changes |

Every benchmark report, release gate, and user-facing workflow report should include a compact Harness Condition Sheet: runtime/model, manifest revision, exposed tools, permission mode, sandbox, verification gates, context policy, telemetry location, retry policy, and cost limits.

### 1.2 Product Quality Bar

The final application should be accepted through four gates:

| Gate | Pass condition | Reject condition |
|---|---|---|
| Feature gate | The API/CLI/MCP surface works on fixtures, validates schemas, records provenance, and fails closed to `unknown` when evidence is insufficient. | A feature can return confident results without typed evidence or provenance. |
| Workflow gate | End-to-end workflows produce a trace, DryRUN prediction where relevant, deterministic gate results, patch-risk verdict, blast-radius/impact report, and non-merge recommendation on uncertainty. | A workflow can present a patch or verdict as resolved after missing, failed, or uncalibrated checks. |
| Operational gate | Runs have replayable run records, complete harness-condition sheets, compliant tool/policy events, budget records, monitor results, and incident/promotion decisions where relevant. | A run is correct-looking but cannot be reconstructed, exceeded budget without checkpointing, used an unauthorized path, skipped required gates, or stores unreviewed memory. |
| Release gate | T1-T4 evals, operational harness gates, calibration, harness ablations, adversarial checks, AI-readiness score, docs, privacy controls, and rollback/diagnosis paths meet stated thresholds. | Readiness is based on a single demo, pass@1, or LLM-as-judge output without independent verification and operational trace replay. |

### 1.3 Local-Agent Development Contract

This implementation plan is also the operating contract for local AI agents that build the package. The product should eventually expose the same controls to users, but the project should use them from the first implementation slice.

| Contract area | Development rule |
|---|---|
| Instruction discovery | Inline shared HC1-HC6 constraints and project policy in `AGENTS.md`; provide `CLAUDE.md` with an `@AGENTS.md` import for Claude Code; use `.github/copilot-instructions.md` and `.codex/INSTRUCTIONS.md` only for runtime-specific guidance; runtime overlays can specialize but cannot relax `AGENTS.md`. |
| Hard constraints | Enforce HC1 no plaintext secrets in repo/prompts/logs/commits; HC2 no writes outside repo/path allowlist; HC3 explicit approval for destructive commands; HC4 no agent-executed irreversible migrations; HC5 deny-by-default network egress; HC6 no red-class data in prompts, tool arguments, or logs. |
| Session workflow | For non-trivial work, the agent records a plan, reads current evidence, edits only within scope, runs the verify path, records verification, and summarizes risk/remaining uncertainty. |
| Permission ladder | Start in plan/read-only for ambiguous or security-sensitive tasks; widen only to scoped edit/execute after scope and commands are known; never use broad bypass modes for CI, releases, or shared repositories. |
| Verify-before-commit | Agent-authored changes require formatter/linter, tests where available, secrets scan, SAST/dependency checks where configured, maintainability review for non-trivial diffs, and a trace/scope audit before commit or PR evidence is accepted. |
| Drift and readiness | Harness artefacts are classified as `missing`, `stale`, `relaxed`, `out-of-stage`, or `clean`; `relaxed` drift blocks release/higher-autonomy work. AI-readiness is a five-axis score and must not regress silently. |
| Memory and lessons | Do not convert session notes into durable policy or memory directly. Promote only reviewed lessons with source links, owner, expiry/review date, acceptance check, and rollback path. |

---

## 2. Feature Dependency Map

| Feature | Summary | Primary Dependencies | Should Be Built Before | Inherited paper anchors |
|---|---|---|---|---|
| F0 - Harness quality substrate | Development-time and release-time controls: supply-chain trust, manifests, permission profiles, sandbox policy, telemetry, verify-before-commit gates, harness condition sheets, stage/drift classification, and AI-readiness scoring | None initially; typed models after Phase 1 | All product features and release gates | `opendev`, `agenttrace`, `aer`, `runtime-governance`, `workstream`, `tdad`, `needle-repo`, `schema-grounded-memory`, `agentic-harness-engineering` |
| F1 - Repository intelligence graph | Typed graph, evidence model, snapshots, summaries, SARIF links, build/test facts | Package skeleton and schemas | All other features | `arise`, `locagent`, `cosil`, `repograph`, `codexgraph`, `repo-aware-kg`, `rig`, `logiclens` |
| F2 - Fault localisation | Relevant files, graph expansion, SARIF/blame/test priors, ranked suspects | F1, SARIF, graph queries | F5, F9, memory retrieval | `fl-context-2026`, `rgfl`, `arise`, `locagent`, `cosil`, `hafixagent`, `repo-aware-kg` |
| F3 - Repo-QA and behaviour tracing | File-location QA, symbol lookup, behaviour graph traversal | F1, MCP query tools, interface plugins | F4, F5, F8 | `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa`, `beyond-code-snippets`, `repochat`, `repograph`, `codexgraph` |
| F4 - Implementation-check | Spec clauses, contracts, graph grounding, static/dynamic verdicts, aggregation | F1, F3, SARIF, contracts, evaluation calibration | Release-quality audit workflows | `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `codespecbench`, `swe-qa`, `coreqa`, `agent-coevo` |
| F5 - Bug-resolve | Investigate, repair, gates, patch risk, blast radius, trajectory recording | F2, F6, F8, SARIF, tests | Memory learning and end-to-end workflow | `agentless`, `fl-context-2026`, `specrover`, `agentic-code-reasoning`, `agent-coevo`, `issue2test`, `assertflip`, `trace-prompt`, `daira` |
| F6 - Patch-review and risk | Diff analysis, SAST delta, contract compatibility, risk classes, merge policy | F1, SARIF, interface plugins, evaluation harness | F5, release gates | `multi-agent-info-theory`, `correct-not-safe`, `redteam-apr`, `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch`, `rig` |
| F7 - SAST alert repair | Alert binding, predicate examples, patch, analyser rerun, SARIF delta | F1, SARIF, F6 gates | F5 vulnerability/security repair | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair`, `codeql-rule-multiagent`, `agent-coevo` |
| F8 - Blast radius | Cross-file, cross-language, cross-repo impact traversal | F1, interface plugins, graph queries | F5, F6, F4 impact reporting | `rig`, `logiclens`, `eagle-x`, `swe-polybench`, `defects4c`, `arise` |
| F9 - Dynamic traces | Runtime capture, scope filtering, trace compression | F2/F3 suspects, graph slices | Ambiguity resolution for F4/F5/F6 | `trace-prompt`, `daira`, `tracerepair`, `agent-coevo` |
| F10 - Memory and replay | Trajectory storage, retrieval, eviction, HER-style relabelling hooks | F5/F6 outputs, evaluation outcomes, graph IDs | Later workflow optimisation | `agent-her`, `evo-memory`, `memory-management-empirical`, `graph-memory-rl`, `c2f-grounded-memory` |
| F11 - Operational harness, telemetry, and continuous improvement | Product runtime plane for run records, harness-condition sheets, policy/tool DAG enforcement, budgets, monitors, operational review, stage/drift classification, readiness audit, incidents, and reviewed lesson promotion | F0 baseline, Phase 1 schemas, Phase 2 stores, Phase 4 MCP/task core; implemented in Phase 4A | F5/F6/F7/F8/F9/F10 workflows, full release gates | `agenttrace`, `aer`, `opendev`, `runtime-governance`, `tokalator`, `cqa`, `agentfixer`, `workstream`, `needle-repo`, `tdad`, `schema-grounded-memory`, `agentic-harness-engineering` |

### 2.1 Named Architecture Surface Checklist

The implementation must preserve the architecture's named surface exactly. Ticket breakdowns may stage the work, but they must not rename, collapse, or silently omit these resources, tools, prompts, or protocol behaviours.

**MCP resources that must exist before production release:**

- `code-intelligence://repos`
- `code-intelligence://schema/graph.schema.json`
- `code-intelligence://schema/run-record.schema.json`
- `code-intelligence://graph/{repo}` as a manifest plus chunk references, not an unconditional full-graph dump
- `code-intelligence://graph/slice/{repo}/{files}`
- `code-intelligence://summary/{repo}/{symbol_path}`
- `code-intelligence://blame/{repo}/{file_path}`
- `code-intelligence://build-evidence/{repo}`
- `code-intelligence://sarif/{repo}/{run_id}`
- `code-intelligence://eval/{run_id}`
- `code-intelligence://memory/{repo}/trajectories`
- `code-intelligence://interfaces`
- `code-intelligence://interfaces/{plugin_id}/{interface_name}`
- `code-intelligence://runs/{run_id}`
- `code-intelligence://runs/{run_id}/harness-condition`
- `code-intelligence://operations/{repo}/ledger`
- `code-intelligence://governance/{repo}/policy`
- `code-intelligence://governance/{repo}/manifest-state`
- `code-intelligence://readiness/{repo}`
- `code-intelligence://incidents/{incident_id}`

**MCP tools and workflow launchers that must exist before production release:**

- Query and evidence tools: `find_callers`, `find_callees`, `get_relevant_files`, `get_graph_slice`, `trace_cross_language`, `git_blame_chain`, `get_interface_contract`, `classify_repo_question`, `answer_repo_question`, `run_static_analysis`, `get_predicate_examples`, and `retrieve_memory`.
- Analysis and verification tools: `classify_patch_risk`, `run_sast_repair`, `compute_rds_features`, `record_eval_result`, `record_trajectory`, and the optional offline `evolve_static_rules`.
- Operational harness tools: `record_run_event`, `record_harness_condition`, `evaluate_tool_policy`, `detect_run_anomalies`, `compare_run_traces`, `assess_harness_stage`, `classify_harness_drift`, `validate_harness_controls`, `compute_readiness_score`, `run_maintainability_oracles`, `run_prompt_manifest_regression`, `promote_operational_lesson`, and `record_incident`.
- Build/update tools: `graph_build`, `graph_update`, `register_repo`, `plugin_reload`, and `memory_compact`.
- Workflow launchers: `run_implementation_check`, `run_issue_resolution`, `run_patch_review`, `run_eval_suite`, `run_operational_review`, and `run_readiness_audit`.
- Live evidence tool: `capture_trace`.

**Prompts and private templates that must exist before workflow completion:**

- Public MCP prompts: `implementation-check`, `bug-resolve`, `patch-review`, `operational-review`, and `readiness-audit`.
- Private skill templates: `investigate`, `repair`, `audit`, `blast-radius`, `sast-repair`, `risk-classify`, and `evaluate`.

**Protocol behaviour that must be implemented, not only documented:**

- Resource subscriptions through `resources/subscribe` and `notifications/resources/updated` for graph, summary, SARIF, interface, eval, memory, run, readiness, governance, and incident resources.
- `notifications/resources/list_changed` when repos or interface plugins are registered or removed.
- Task-capable tools with task descriptors, `CreateTaskResult` / `taskId` handling, persistence, `tasks/get`, `tasks/result`, optional `tasks/list`, `tasks/cancel`, progress and `notifications/tasks/status`, TTL, restart recovery, high-entropy task IDs, and authorization binding where the transport supports authorization.
- Optional MCP Sampling capability negotiation for parallel review subagents; when unsupported, workflows must fall back to a local LLM/reviewer interface while preserving the same run-record events and gates.

---

## 3. Implementation Phases

### Phase H0 - Harness Quality Foundation

**Purpose:** Establish the operational envelope that will keep the implementation and final application reliable. This phase starts before Phase 0 and remains active through every later phase.

**Architecture coverage:**

- F0 harness quality substrate
- Development-time and product-time governance
- Release-quality definition for all later phases

**Harness anchors:** `opendev`, `agenttrace`, `aer`, `runtime-governance`, `tokalator`, `workstream`, `tdad`, `needle-repo`, `agentic-harness-engineering`, `schema-grounded-memory`.

**Build:**

- Repo-local control-plane manifests:
  - `AGENTS.md` for HC1-HC6 hard constraints, success definition, assessment rubric, scope boundary, data policy, quality gate, cost policy, data classes, and enforcement hooks.
  - inlined HC1-HC6 default constraints: no plaintext secrets; no writes outside the repo/path allowlist; explicit human approval for destructive commands; no agent-executed irreversible migrations; deny-by-default network egress; no red-class data in prompts, tool arguments, or logs.
  - runtime overlays for Claude Code, Codex CLI, GitHub Copilot, Cursor, or similar tools only where runtime-specific behaviour is required, with `CLAUDE.md` importing `@AGENTS.md` and non-relaxation checks against `AGENTS.md`.
  - `.agent/plan.md` template for session contracts.
  - `SKILL.md` templates for test-first repair, safe refactor, dependency update, SAST repair, evaluation, and release.
- Stage-aware maturity model:
  - `S0` greenfield: branch discipline, baseline manifests, plan template, sandbox, secret-safe gitignore, pre-commit.
  - `S1` walking skeleton: tests/lint in CI, command allowlist, session logging, governance workflow.
  - `S2` growing: tool DAG, manifest regression suite, schema-grounded memory controls, SAST/dependency/license scans, maintainability gate, readiness score in CI.
  - `S3` production: held-out evals, adversarial sweeps, provenance ledger for skills/MCP/prompt assets, incident runbook, governed harness evolution.
  - monotonic upgrade rule: a later stage can add or specialize controls, but cannot remove or weaken lower-stage controls.
- Tool and permission model:
  - read/search/edit/execute/review/commit tool categories.
  - deny-first permission modes.
  - path allowlists.
  - network policy.
  - sandbox/devcontainer baseline.
- Live telemetry contract:
  - session start/end.
  - plan updates.
  - tool calls and results.
  - context assembly and compaction events.
  - token/cost/wall-clock metrics.
  - diff snapshots.
  - verification events.
  - human approvals and rejections.
- Product run-record contract:
  - `run_id`, workflow, repository scope, model/backend, toolset hash, permission profile, policy ID, context budget, and redaction policy.
  - typed run events with sequence, actor, stage, input/output artefact references, policy outcome, token count, wall time, and redaction status.
  - append-only operational ledger for anomalies, budget overruns, denied actions, incidents, and promotion decisions.
- Verify-before-commit command set:
  - format/lint.
  - unit and integration tests.
  - secrets scan.
  - SAST.
  - dependency scan.
  - domain invariant hooks.
  - maintainability checks where expressible.
- Harness Condition Sheet template for every evaluation and release report.
- Operational review template for trace completeness, policy compliance, budget behaviour, anomaly diagnosis, incident follow-up, and promotion candidates.
- AI-readiness score covering agent config, docs, CI/CD, code structure, security, and evaluation coverage.
- AI-readiness rubric and thresholds:
  - five axes: agent config, documentation, CI/CD, code structure, and security.
  - score range: 0-25.
  - stage gates: `S0 -> S1` needs 5 total and at least 1 per axis; `S1 -> S2` needs 12 total and at least 2 per axis; `S2 -> S3` needs 18 total and at least 3 per axis; stable `S3` needs 22 total and at least 4 per axis.
  - no-regression check: a harness change fails unless any readiness-axis drop is tied to an explicit reviewed waiver or incident.
- Harness drift classifier for repo/project artefacts:
  - `missing`
  - `stale`
  - `relaxed`
  - `out-of-stage`
  - `clean`
- Readiness report with per-axis no-regression checks.
- Supply-chain and provenance ledger for the agent stack:
  - pinned runtime, MCP server, language backend, analyser, prompt asset, skill, and dependency versions.
  - hash/signature metadata where practical.
  - dependency and secret-scan evidence for lockfile or tool-manifest changes.
  - prompt/document-injection canaries for risky repository text and external tool output.
- Manifest/tool-description regression test skeleton:
  - visible behaviour cases.
  - hidden policy cases.
  - tool-order cases.
  - semantic mutation cases.
  - spec-evolution cases.
- Incident record template:
  - impact.
  - timeline.
  - root cause.
  - containment.
  - remediation.
  - evidence links.
  - detector or eval follow-up.
  - reviewer closure.

**Dependency notes:**

- H0 is both a development process requirement and a product requirement.
- Do not wait until Phase 18 to add observability or verification; later calibration is useless without early traces.
- The first version can be file-based and simple, but it must be structured enough to be parsed by release gates.

**Exit criteria:**

- Every implementation phase can declare its Harness Condition Sheet.
- Every workflow-producing phase has a session trace and verification record.
- A parseable run-record schema exists before workflow implementation begins, even if the first writer is file-based.
- A local `verify` path exists and is documented.
- Manifest and tool-description changes have tests or documented review criteria.
- Operational review and incident templates are available for failed runs.
- The current repository has an assessed harness stage, readiness score, and explicit next-stage controls.
- Harness drift checks reject relaxed policy changes, such as disabling secrets scans or bypassing permissions.
- AI-readiness reports are comparable over time and fail the release gate when a readiness axis regresses without an accepted waiver.
- Feature readiness is not accepted from a demo run without telemetry, verification, and evaluation artefacts.

---

### Phase 0 - Python Package Skeleton

**Purpose:** Establish a maintainable Python project foundation before implementing product logic.

**Inherited paper anchors:** `survey-yang-2025`, `survey-issue-resolution-2026`, `agentless`.

**Build:**

- Python package scaffold.
- Dependency management with pinned/runtime-reportable versions.
- Test runner and lint/type-check setup.
- Pre-commit or equivalent local verify entrypoint.
- Initial CI workflow for lint, type checks, tests, secrets, and dependency scanning.
- Configuration model.
- Logging and structured error model.
- Session telemetry skeleton and trace writer.
- Run-record writer skeleton.
- Policy evaluator skeleton.
- Budget monitor skeleton.
- Initial CLI entrypoint.
- Placeholder MCP server entrypoint.
- Plugin registry skeleton.
- Permission/profile configuration skeleton for MCP tools and workflow commands.
- Basic fixture repositories for tests.

**Key modules likely needed:**

- `config`
- `schemas`
- `graph`
- `indexing`
- `mcp_server`
- `plugins`
- `sarif`
- `workflows`
- `evaluation`
- `harness`
- `memory`
- `operations`
- `telemetry`
- `governance`

**Exit criteria:**

- Package installs locally.
- Test suite runs.
- Local verify command runs the same core checks expected before merge.
- CLI can print version and config.
- Empty MCP server can start in development mode.
- Plugin registry can load a no-op plugin.
- Runtime/tool versions and the active Harness Condition Sheet can be printed.
- A dummy run can create a run record, append an event, and close with a status.

---

### Phase 1 - Shared Schemas and Evidence Model

**Purpose:** Implement the typed data contracts that every later phase depends on.

**Architecture coverage:**

- F1 foundation
- Shared evidence and verdict model
- Graph schema
- Contract artefact schema
- Patch and verdict schema
- Run-record and operational event schema
- Snapshot and provenance model

**Inherited paper anchors:** `rig`, `arise`, `repograph`, `codexgraph`, `logiclens`, `predicatefix`, `codespecbench`, `compass`, `pvbench`, `agenttrace`, `aer`, `opendev`, `runtime-governance`.

**Build:**

- Versioned `graph.schema.json`.
- Python models for:
  - repositories
  - files
  - symbols
  - graph nodes
  - graph edges
  - spans
  - provenance
  - snapshots
  - SARIF references
  - interface records
  - contract artefacts
  - patches
  - verdicts
  - evidence bundles
  - run records
  - run events
  - operational ledger entries
  - tool-call events
  - approval/denial events
  - budget events
  - compaction events
  - monitor alerts
  - incidents
  - promotion candidates
  - session traces
  - tool permissions
  - policy decisions
  - context budgets
  - verification events
  - maintainability oracle results
  - prompt/manifest regression results
  - Harness Condition Sheets
  - harness stages and drift findings
  - hard constraints and manifest precedence records
  - AI-readiness reports
  - readiness-axis score histories
  - supply-chain provenance records for runtimes, MCP servers, prompt assets, skills, analysers, and dependencies
- Graph node type enum matching the architecture:
  - repository structure: `repo`, `package`, `directory`, `file`, `module`
  - code symbols: `class`, `function`, `method`, `variable`, `type`, `interface`
  - interface boundaries: `idl_interface`, `http_route`, `websocket_event`, `grpc_service`, `protobuf_message`
  - specification/contracts: `document`, `design_clause`, `intent_node`, `contract_artifact`, `generated_test`, `predicate`
  - evidence: `test`, `runtime_trace`, `sast_rule`, `sarif_alert`, `build_target`, `ci_job`, `eval_run`
  - change/review: `patch`, `diff_hunk`, `risk_finding`, `verdict`
  - memory: `trajectory`, `issue_class`, `fl_decision`, `patch_class`, `outcome`
  - operational harness: `session`, `run_record`, `run_event`, `harness_condition`, `permission_profile`, `tool_policy`, `tool_call`, `approval`, `budget_event`, `compaction_event`, `monitor_alert`, `incident`, `readiness_score`, `maintainability_oracle`, `manifest_regression`
- Graph edge type enum matching the architecture:
  - code and evidence edges: `contains`, `imports`, `calls`, `dataflow`, `tests`, `documents`, `decomposes_to`, `checks`, `satisfies`, `violates`, `implements`, `exposes`, `consumes`, `ffi`, `nullable`, `owns`, `instantiates`, `warned_by`, `fixed_by`, `changed_by`, `observed_in`
  - operational edges: `used_tool`, `approved_by`, `denied_by`, `verified_by`, `blocked_by`, `compacted_to`, `promoted_to`, `triggered_incident`
- Contract artefact schema fields:
  - `clause_id`
  - `language`
  - `artifact_type`
  - `target_symbols`
  - `source_clause_span`
  - `compile_status`
  - `last_run_status`
  - `confidence`
- Patch, risk-finding, and verdict schema fields:
  - `diff_id`
  - `changed_symbols`
  - `sarif_delta_id`
  - `test_delta_id`
  - `risk_class`
  - `calibrated_probability`
  - `ece_bucket`
  - `policy_action`
- Run-record and run-event required fields:
  - run record: `run_id`, `workflow`, `user_intent_hash`, `repos`, `start_ts`, `end_ts`, `status`, `model_backend`, `toolset_hash`, `policy_id`, `permission_profile`, `context_budget`, `run_event_count`, `harness_condition_id`, `final_verdict_id`, `incident_ids`, and `redaction_policy`
  - run event: `event_id`, `run_id`, `seq`, `ts`, `type`, `actor`, `stage`, `input_ref`, `output_ref`, `policy_action`, `token_count`, `wall_ms`, `artefact_ids`, and `redaction_status`
- Confidence and derivation enums:
  - `parser`
  - `analyser`
  - `build`
  - `test`
  - `trace`
  - `llm`
  - `heuristic`
  - `policy`
  - `review`
- Common verdict values:
  - `satisfied`
  - `violated`
  - `safe`
  - `risky`
  - `unknown`
  - `process-compliant`
  - `process-noncompliant`
  - `trace-incomplete`
  - `budget-exhausted`
  - `needs-readiness-work`
  - workflow-specific extensions
- Shared verdict payload fields:
  - `verdict`
  - `confidence`
  - `evidence`
  - `run_record`
  - `reasoning_chain`
  - `uncertainty`
  - `recommended_action`
- Evidence-strength enum or ordering:
  - hard static evidence.
  - hard dynamic evidence.
  - structured repository evidence.
  - calibrated model evidence.
  - soft LLM evidence.
- Validation helpers.
- Serialization and deserialization tests.

**Dependency notes:**

- Do this before storage, MCP, indexing, SARIF, or workflows.
- Do not add LLM-specific behaviour here except for marking derivation and confidence.

**Exit criteria:**

- All schema objects round-trip through JSON.
- Invalid graph edges and missing provenance fail validation.
- Every graph fact can carry `repo`, `git_sha`, optional `worktree_snapshot_id`, `file`, `span`, `confidence`, and `derivation`.
- Every long-running task and workflow can attach trace events, permission mode, context budget, verification results, and Harness Condition Sheet metadata.
- Every long-running task and workflow can attach a run record with stage/tool/context/gate/monitor/review events.
- Operational events are append-only, sequence-numbered, and redaction-aware.
- Incidents and promotion candidates reference source run/event IDs.
- Schema changes that affect manifests, tool descriptions, or workflow gates have regression tests.

---

### Phase 2 - Local Graph Store and Repository Registry

**Purpose:** Provide the local persistence layer and repo registration mechanics.

**Architecture coverage:**

- F1 graph persistence
- F11 operational evidence persistence
- Multi-repository workspace
- Snapshot-aware evidence retention

**Inherited paper anchors:** `rig`, `logiclens`, `graph-memory-rl`, `hafixagent`, `agenttrace`, `aer`, `schema-grounded-memory`.

**Build:**

- Repository registry.
- Workspace metadata store.
- Harness metadata store:
  - active manifest hashes
  - permission profile
  - sandbox/runtime descriptor
  - verification gate versions
  - dependency/analyser versions
- Operational store:
  - run records
  - run events
  - harness-condition sheets
  - policy decisions
  - budget/compaction events
  - monitor alerts
  - incidents
  - readiness reports
  - promotion records
- Local graph store.
- Graph query primitives:
  - add nodes
  - add edges
  - fetch by ID
  - fetch by type
  - fetch neighbours
  - fetch ego graph
  - fetch by file/span
- Snapshot tracking:
  - committed `git_sha`
  - dirty-worktree snapshot ID
  - branch
  - index freshness status
- Basic graph export/import.

**Dependency notes:**

- Storage can start simple, for example SQLite plus JSON columns, DuckDB, or a local graph abstraction.
- The first version should optimise correctness and auditability, not large-scale performance.

**Exit criteria:**

- `register_repo` stores repository metadata.
- Graph facts can be added and queried.
- Dirty worktree snapshots are represented.
- Mixed-snapshot queries are detectable.
- Stored evidence can be tied back to the harness condition under which it was produced.
- Run records can be queried by repo, workflow, status, incident type, and time.
- Incidents and promotion records retain links to source run events and artefacts.

---

### Phase 3 - Repository Indexing MVP

**Purpose:** Build the first deterministic repository intelligence graph.

**Architecture coverage:**

- F1 repository intelligence graph
- `graph_build`
- `graph_update`
- `code-intelligence://repos`
- `code-intelligence://graph/{repo}`
- `code-intelligence://graph/slice/{repo}/{files}`
- `code-intelligence://summary/{repo}/{symbol_path}`
- `code-intelligence://blame/{repo}/{file_path}`

**Inherited paper anchors:** `arise`, `locagent`, `repograph`, `codexgraph`, `rig`, `hafixagent`, `swe-polybench`.

**Build:**

- File tree scanner.
- Git metadata collector.
- Git blame-chain collector for file/line evidence and parent commit history.
- Universal ctags adapter.
- Tree-sitter adapter for basic syntax facts.
- Python import/symbol indexing MVP.
- Build/test evidence detector MVP:
  - pytest
  - package manager files
  - common test directories
- Lazy symbol-summary cache:
  - generated on first access.
  - keyed by repo, symbol path, `git_sha`, and dirty-worktree snapshot.
  - invalidated whenever the owning file changes.
  - stored as low-confidence or hybrid evidence, never as parser fact.
- Incremental update by changed files.
- Incremental update of affected summaries, SARIF bindings, blame metadata, and cross-language/interface links when the relevant backends are present.
- Graph slice generation around files and symbols.
- Full-graph manifest generation with chunk references; large graph resources must not default to full JSON dumps.
- Run events for indexing:
  - files scanned.
  - backend versions.
  - indexing diagnostics.
  - stale/dirty snapshot warnings.
  - skipped files and reasons.

**Dependency notes:**

- Start with Python repositories because they support fast iteration.
- Add other language-specific backends later.
- Do not block the core graph design on perfect call graph precision.

**Exit criteria:**

- `graph_build(repo_path)` indexes a small Python repo.
- `graph_update(repo_path)` updates changed files without rebuilding everything.
- Graph slices include files, symbols, imports, tests, and provenance.
- Symbol summaries and blame chains can be cached, invalidated, and retrieved with snapshot provenance.
- Stale index state is visible.
- Graph build/update runs produce operational events and can be reviewed when an index is incomplete or stale.

---

### Phase 4 - MCP Server Core

**Purpose:** Expose the index through stable MCP resources, tools, prompts, tasks, and notifications.

**Architecture coverage:**

- MCP resources
- MCP tools
- MCP prompt templates
- Async task model
- Resource update notifications

**Inherited paper anchors:** `rig`, `logiclens`, `predicatefix`, `swe-bench-live`, `swd-bench`, `swe-polybench`.

**Build:**

- MCP server runtime.
- Resource routing for:
  - `code-intelligence://repos`
  - `code-intelligence://schema/graph.schema.json`
  - `code-intelligence://schema/run-record.schema.json`
  - `code-intelligence://graph/{repo}`
  - `code-intelligence://graph/slice/{repo}/{files}`
  - `code-intelligence://summary/{repo}/{symbol_path}`
  - `code-intelligence://blame/{repo}/{file_path}`
  - `code-intelligence://build-evidence/{repo}`
- Query tools:
  - `register_repo`
  - `graph_build`
  - `graph_update`
  - `plugin_reload`
  - `get_graph_slice`
  - `find_callers`
  - `find_callees`
  - `git_blame_chain`
- Task wrapper for long-running operations.
- Task descriptors for long-running tools, including `execution.taskSupport`.
- Task persistence, `tasks/get` polling, optional `tasks/list`, `tasks/cancel`, `tasks/result` retrieval, `notifications/tasks/status`, progress status, TTL, restart recovery, and high-entropy task IDs.
- Authorization binding for task state/results where the transport supports authorization; disable broad task listing for local unauthenticated multi-user scenarios.
- `resources/subscribe` support and `notifications/resources/updated` after graph, summary, blame, SARIF, interface, eval, memory, run, readiness, governance, or incident changes.
- `notifications/resources/list_changed` when a repo or interface plugin is added, removed, or reloaded.
- Optional MCP Sampling capability negotiation for review subagents; unsupported clients must receive an explicit fallback path.
- Tool permission descriptors:
  - required mode
  - path scope
  - network requirement
  - side-effect class
  - approval requirement
- MCP/tool-description regression tests for tool order, refusal, and policy-compliance cases.
- Task telemetry emission for progress, command/tool calls, costs, cancellation, and errors.
- Public prompt stubs:
  - `implementation-check`
  - `bug-resolve`
  - `patch-review`
  - `operational-review`
  - `readiness-audit`

**Dependency notes:**

- Keep MCP tool results schema-first.
- Workflow prompts should assemble instructions and suggested tools, not directly execute long workflows yet.

**Exit criteria:**

- MCP client can list resources and call graph tools.
- Long-running `graph_build` can run as a task.
- Resource subscriptions and update/list-changed notifications fire for graph, summary, repo, and plugin changes.
- MCP tools expose permission metadata and produce trace events.
- Task events are linked to run records where a workflow/task run exists.
- Task IDs are high-entropy, TTL-bound, and recoverable after server restart within policy.
- Sampling capability is detected and recorded in the Harness Condition Sheet.
- Prompt/tool-description changes are covered by regression tests or explicit review criteria.

---

### Phase 4A - Operational Harness Runtime Plane

**Purpose:** Implement F11 as product runtime functionality: every workflow can be recorded, governed, budgeted, monitored, reviewed, and improved from structured evidence.

**Architecture coverage:**

- F11 operational harness, telemetry, and continuous improvement
- `code-intelligence://runs/{run_id}`
- `code-intelligence://runs/{run_id}/harness-condition`
- `code-intelligence://operations/{repo}/ledger`
- `code-intelligence://governance/{repo}/policy`
- `code-intelligence://governance/{repo}/manifest-state`
- `code-intelligence://readiness/{repo}`
- `code-intelligence://incidents/{incident_id}`
- `record_run_event`
- `record_harness_condition`
- `evaluate_tool_policy`
- `detect_run_anomalies`
- `compare_run_traces`
- `assess_harness_stage`
- `classify_harness_drift`
- `validate_harness_controls`
- `compute_readiness_score`
- `run_maintainability_oracles`
- `run_prompt_manifest_regression`
- `promote_operational_lesson`
- `record_incident`
- `run_operational_review`
- `run_readiness_audit`

**Inherited paper anchors:** `agenttrace`, `aer`, `opendev`, `runtime-governance`, `tokalator`, `cqa`, `agentfixer`, `agent-drift`, `workstream`, `needle-repo`, `tdad`, `schema-grounded-memory`, `agentic-harness-engineering`.

**Build:**

- Run lifecycle API:
  - create run.
  - append run event.
  - close run.
  - mark run blocked/failed/unknown.
  - link run to task IDs and artefacts.
- Harness-condition API:
  - capture model/backend.
  - capture server/skill/prompt/tool versions.
  - capture permission profile and effective policy.
  - capture sandbox/network/context/budget policy.
  - capture verification gates and redaction policy.
- Operational resources:
  - `runs`.
  - `harness-condition`.
  - `operations/ledger`.
  - `governance/policy`.
  - `governance/manifest-state`.
  - `readiness`.
  - `incidents`.
- Harness stage and drift APIs:
  - assess `S0`/`S1`/`S2`/`S3` stage from source/test/CI/release/agent-config signals.
  - parse `AGENTS.md`, runtime overlays (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`), skills, hooks, tool descriptions, and CI policy.
  - classify artefacts as `missing`, `stale`, `relaxed`, `out-of-stage`, or `clean`.
  - block `relaxed` drift until reviewed.
  - compute next-stage controls without skipping lower-stage requirements.
- Policy engine MVP:
  - stage-aware tool DAG.
  - path allowlist checks.
  - network policy checks.
  - side-effect class checks.
  - allow/deny/approval-required decisions.
- Budget manager:
  - token budget.
  - tool-call budget.
  - retry budget.
  - wall-clock budget.
  - artefact/trace-size budget.
  - soft warning and hard-stop/checkpoint decisions.
- Monitor detectors:
  - repeated identical tool calls.
  - repeated failing gate with no code/evidence change.
  - context growth without new evidence.
  - denied-operation storm.
  - budget exhaustion.
  - stale or mixed snapshot evidence.
  - out-of-scope write attempt.
  - missing required verification.
  - secret/redaction failure.
  - cumulative-risk pattern placeholder.
- Operational review workflow:
  - trace completeness check.
  - policy compliance check.
  - budget behaviour report.
  - anomaly list.
  - gate adequacy report.
  - incident follow-up report.
  - promotion-candidate report.
- Readiness audit workflow:
  - detected harness stage and next-stage recommendation.
  - agent config.
  - documentation/spec links.
  - CI/build/test availability.
  - code structure.
  - security scans.
  - deterministic gate coverage.
  - per-axis no-regression result.
- Incident workflow:
  - open incident from monitor/reviewer.
  - attach evidence links.
  - record containment/remediation/root cause.
  - require detector or eval follow-up for P0/P1 incidents.
  - close with reviewer sign-off.
- Promotion workflow:
  - promote reviewed lesson to schema-grounded memory, detector, eval regression, static-analysis rule, readiness task, or governance policy.
  - reject unreviewed prose memory.
  - record owner, expiry/review date, source links, and rollback path.

**Dependency notes:**

- This phase should land before patch-producing workflows become serious, because later workflow confidence depends on run records and policy events.
- The first implementation can store JSONL and SQLite records locally; the contract matters more than the storage backend.
- Policy enforcement belongs in deterministic code. LLM summaries can explain a violation but cannot waive it.

**Exit criteria:**

- A workflow task can create a run, append stage/tool/context/gate/monitor/review events, and close with a final status.
- `run_operational_review(run_id)` returns `process-compliant`, `process-noncompliant`, `trace-incomplete`, `budget-exhausted`, or `needs-readiness-work` with evidence.
- `run_readiness_audit(repo)` returns a score and concrete missing controls.
- `assess_harness_stage(repo)` returns a stage and next-stage controls, and `classify_harness_drift(repo)` blocks `relaxed` drift.
- `validate_harness_controls(repo)` runs manifest non-relaxation, readiness no-regression, and prompt/tool-description regression checks for the detected stage.
- Denied tool/path/network actions are recorded and can block a run.
- Budget hard stops checkpoint or force `unknown`; they do not silently produce confident verdicts.
- Incidents can be opened, linked to evidence, and closed with remediation.
- Promotion candidates cannot become durable memory/policy/eval changes without review metadata.

---

### Phase 5 - Language Backend Expansion

**Purpose:** Expand deterministic graph coverage across the target languages.

**Architecture coverage:**

- F1 multi-language graph
- Intra-language indexing backends
- C/C++, Python, JavaScript/TypeScript target support

**Inherited paper anchors:** `arise`, `locagent`, `marscode`, `rig`, `swe-polybench`, `defects4c`, `predicatefix`.

**Build:**

- Python:
  - `pyan3` adapter for call/import graph.
  - Pyright/Pylance or LSP adapter where practical.
- JavaScript/TypeScript:
  - `ts-morph` or `madge` adapter.
  - package metadata and test runner detection.
- C/C++:
  - `libclang` or `clangd` adapter.
  - `bear` / `compile_commands.json` support.
  - CMake File API / CTest evidence where available.
- Optional Java benchmark/customer parity backend:
  - JDT or CodeQL Java for symbol, call, generic-instantiation, and nullness edges when Java projects enter Vul4J, SWE-PolyBench-style, or customer corpora.
- LSP abstraction for references, definitions, and diagnostics.
- Backend capability reporting.
- Cross-checking between parser, ctags, and LSP facts.

**Dependency notes:**

- Backends emit the common graph schema only.
- Backend-specific confidence must be preserved.
- Missing backends should degrade to partial evidence, not break the whole index.

**Exit criteria:**

- Python, JS/TS, and C/C++ repositories produce symbols/imports.
- At least one call graph backend works per target language where tooling is available.
- Optional Java support has an explicit capability flag and can be exercised by Java calibration fixtures when enabled.
- Backend errors are captured as index diagnostics.

---

### Phase 6 - SARIF and Static Analysis Layer

**Purpose:** Make static-analysis alerts first-class graph evidence.

**Architecture coverage:**

- SARIF v2.1.0 analyser-data contract
- `run_static_analysis`
- `code-intelligence://sarif/{repo}/{run_id}`
- `warned_by` graph edges
- F7 foundation
- F6 SAST delta foundation

**Inherited paper anchors:** `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair`, `codeql-rule-multiagent`, `logiceval`.

**Build:**

- SARIF parser and normalizer.
- SARIF run store.
- Alert-to-file/span binding.
- Alert-to-symbol binding where possible.
- `warned_by` graph edges.
- Semgrep adapter.
- Bandit adapter for Python.
- Optional CodeQL adapter.
- Optional SonarQube, GitHub Advanced Security, or project-specific SARIF import adapter.
- Rule metadata and predicate ID extraction where the analyser exposes it.
- Severity/rule-family normalization.
- SARIF before/after diff utility.

**Dependency notes:**

- SARIF import should work even when the analyser was run externally.
- The graph should keep SAST alerts separate from verdicts.

**Exit criteria:**

- `run_static_analysis(repo, ruleset)` stores normalized SARIF.
- Alerts are linked to graph nodes where possible.
- External SARIF import preserves analyser name, rule ID, predicate ID where available, severity, locations, and provenance.
- SARIF delta can identify appeared, disappeared, and changed alerts.

---

### Phase 7 - Cross-Language Interface Plugin System

**Purpose:** Implement default cross-language and cross-repository reasoning.

**Architecture coverage:**

- Interface plugin contract
- `code-intelligence://interfaces`
- `code-intelligence://interfaces/{plugin_id}/{interface_name}`
- `trace_cross_language`
- F8 foundation

**Inherited paper anchors:** `rig`, `logiclens`, `eagle-x`, `mids-valve`, `jml-autodoc`, `swe-polybench`, `defects4c`.

**Build:**

- Plugin interface:
  - `detect`
  - `index`
  - `link`
  - `traverse`
- `InterfaceRecord` model.
- Plugin capability registration.
- Interface resources.
- Traversal integration with graph queries.
- Built-in plugin MVPs:
  - HTTP-REST
  - WebSocket
  - omniORB-IDL
- `plugin_reload(plugin_id?)` re-runs a plugin indexing pass and emits resource-list/update notifications.
- HTTP-REST plugin details:
  - consume OpenAPI/Swagger documents first when available.
  - fall back to Semgrep/framework adapters for FastAPI, Flask, Django, `fetch`, axios, and similar clients.
  - normalise equivalent path patterns such as `/users/:id`, `/users/{id}`, and `/users/<id>`.
  - record method, path, request/response schema, status-code contract, auth hints, and confidence.
- WebSocket plugin details:
  - detect socket.io registration and emission sites.
  - extract event names and payload-shape hints from TypeScript types, Pydantic/dataclass models, JSON-schema literals, or validation code.
  - emit dynamic event names as low-confidence candidates unless statically finite.
- omniORB-IDL plugin details:
  - use `omniidl -p` or equivalent IDL AST output.
  - link IDL definitions to C++ POA skeletons, servant implementations, Python generated stubs, and Python callers.
  - preserve generated artefacts and avoid recommending manual edits to generated stubs.
- Future plugin backlog:
  - gRPC
  - Protobuf
  - ZeroMQ
  - MQTT
  - DBUS
- Confidence model for exact, inferred, and ambiguous links.

**Dependency notes:**

- HTTP-REST is likely the easiest first plugin because route/client detection can start with Semgrep and simple framework adapters.
- omniORB-IDL can follow once C/C++ and Python indexing are stable.
- Ambiguous interface links must be exposed as candidates, not confirmed impact.

**Exit criteria:**

- `trace_cross_language(start_symbol)` can cross at least one plugin boundary.
- Interface contracts are available as resources.
- Cross-repo traversal works when two registered repos are linked by an interface.

---

### Phase 8 - Repository Query and Repo-QA MVP

**Purpose:** Provide evidence-cited repository questions and graph behaviour tracing.

**Architecture coverage:**

- F3 repo-QA and behaviour tracing
- `classify_repo_question`
- `answer_repo_question`
- `get_interface_contract`
- `git_blame_chain`
- `code-intelligence://blame/{repo}/{file_path}`

**Inherited paper anchors:** `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa`, `beyond-code-snippets`, `repochat`, `repograph`, `codexgraph`, `hafixagent`.

**Build:**

- Question classifier:
  - `file-loc`
  - `symbol-loc`
  - `behaviour-trace`
  - `contract-check`
  - `other`
- Deterministic symbol/file lookup.
- Graph-path answer builder.
- Behaviour-trace graph traversal.
- Interface-contract lookup.
- Git blame chain resource/tool.
- LLM answer synthesis behind a typed evidence interface.
- Confidence rules by question class.

**Dependency notes:**

- File-location answers can reach automation earlier than behaviour-tracing answers.
- Behaviour-tracing answers should remain supporting evidence until graph-augmented `swe-qa` / `coreqa` behaviour subsets meet the architecture's >=70% ship gate.
- File-location acceptance should use `swd-bench` Functionality-Localization or a faithful local equivalent, not LLM-as-judge scores.

**Exit criteria:**

- File-location questions return cited files/symbols.
- Behaviour-trace questions return graph paths or `unknown`.
- Answers that lack graph/code evidence cannot be marked high confidence.

---

### Phase 9 - Fault Localisation

**Purpose:** Rank likely root-cause locations and produce a bounded context set.

**Architecture coverage:**

- F2 fault localisation and relevant-context discovery
- Private `investigate` template foundation
- `get_relevant_files`

**Inherited paper anchors:** `fl-context-2026`, `rgfl`, `arise`, `locagent`, `cosil`, `hafixagent`, `repo-aware-kg`, `autocoderover`, `agentless`.

**Build:**

- Issue text normalizer:
  - symptoms
  - expected behaviour
  - observed behaviour
  - mentioned APIs/files
  - error strings
- Candidate retrieval:
  - keyword search
  - semantic embeddings interface with per-symbol vector cache invalidated by `git_sha` / worktree snapshot changes
  - SARIF proximity
  - document/spec links
  - blame/history prior
  - coarse memory hints when F10 is available, with low-utility records rejected rather than silently used
- Graph-neighbour expansion:
  - callers
  - callees
  - imports
  - tests
  - documents
  - data-flow
  - interface edges
- Optional SBFL/Ochiai feature when coverage/failing tests exist.
- Bounded context assembler:
  - graph slices.
  - cached symbol summaries from `code-intelligence://summary/{repo}/{symbol_path}`.
  - SARIF/build/test evidence.
  - exact source spans only when required for the next decision.
- Candidate explanation schema.
- Ranking policy.
- Uncertainty model.

**Dependency notes:**

- Start with file-level ranking, then add symbol/line narrowing.
- Keep the default context budget near the architecture's 6-10 relevant-file guidance.

**Exit criteria:**

- `get_relevant_files(issue_text)` returns ranked files with evidence.
- `investigate` returns suspect symbols/files with reasoning and uncertainty.
- Retrieved summaries, memory hints, graph slices, and exact code spans are all separately attributed.
- Low agreement between semantic retrieval and graph/static evidence produces an uncertain localisation.

---

### Phase 10 - Evaluation Harness Baseline

**Purpose:** Establish measurement before adding high-level repair automation.

**Architecture coverage:**

- Evaluation harness
- T1/T2 benchmark ladder foundation
- F11 operational-quality measurement
- RDS v0.2 logging
- `code-intelligence://eval/{run_id}`
- `run_eval_suite`
- `compute_rds_features`
- `record_eval_result`

**Inherited paper anchors:** `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench`, `swe-bench-illusion`, `swe-qa-pro`, `livecoder`, `swe-rebench-v2`, `pvbench`, `agenttrace`, `aer`, `runtime-governance`, `tokalator`, `workstream`, `needle-repo`.

**Build:**

- Evaluation run model.
- Harness Condition Sheet model and renderer:
  - runtime/model
  - manifest hashes
  - tool set
  - permission mode
  - sandbox/network policy
  - verification gates
  - context/cost policy
  - retry policy
  - telemetry location
- Benchmark adapter interface.
- Local smoke benchmark format.
- T1 smoke runner.
- T2 regression runner skeleton.
- Private `evaluate` template that launches `run_eval_suite` and logs resolve-rate, FL-conditioned repair rate, PoC+ pass-rate, repo-QA accuracy, cross-language drift, RDS v0.2 features, contamination canaries, and operational-quality metrics.
- Repeated-trial and perturbation runner skeleton for reliability surfaces.
- Flaky-test detection and exclusion metadata.
- Prompt, manifest, and MCP tool-description regression test adapter.
- Structural maintainability oracle adapter:
  - change locality
  - dependency direction
  - responsibility decomposition
  - reuse of existing abstractions
  - side-effect isolation
  - testability
- AI-readiness report generator:
  - agent config
  - documentation
  - CI/CD
  - code structure
  - security
- Operational-quality metrics:
  - process compliance rate.
  - trace replay success rate.
  - policy violation count.
  - budget hard-stop count.
  - incident recidivism rate.
  - promotion precision placeholder.
  - cost per accepted verdict.
  - readiness delta.
- FL metrics:
  - top-1
  - top-3
  - top-N
  - resolve-rate conditioned on correct FL
- RDS feature computation:
  - `files_touched`
  - `chain_depth`
  - `cross_file_dataflow`
  - `ambient_warning_load`
  - `test_brittleness`
  - `memorisation_distance`
- Eval resource.
- Contamination/freshness metadata fields.
- Mandatory reporting rules:
  - use `swe-bench-live`, not SWE-bench Verified, as the headline resolve-rate.
  - log suite median age and refresh `swe-bench-live` monthly for external-quality reporting.
  - report PoC+ pass-rate alongside vulnerability-class repair results.
  - use `swd-bench` Functionality-Localization for repo-QA file-location acceptance.
  - avoid LLM-as-judge as a release-gate substitute.
  - report resolve-rate conditioned on correct fault localisation.
  - log RDS v0.2 as a six-axis feature vector until the cross-benchmark regression is published.

**Dependency notes:**

- Use small local fixtures first.
- Add external benchmark adapters incrementally.

**Exit criteria:**

- A smoke eval run produces stored metrics.
- Every eval run records a Harness Condition Sheet.
- RDS features are computed and saved per instance.
- Eval reports are reproducible from stored artefacts.
- Eval reports include operational metrics beside task metrics.
- Baseline suite contains at least one ambiguity task, one security-sensitive task, and one maintainability task where passing public tests alone is insufficient.
- Manifest/tool-description regression cases can fail independently of code tests.

---

### Phase 11 - Patch Review and Risk Gates

**Purpose:** Build the safety and correctness gate that repair workflows must pass.

**Architecture coverage:**

- F6 patch-review and patch-risk classification
- F11 operational run compliance for patch-producing and patch-review workflows
- Private `audit` mode for patches
- `run_patch_review`
- `classify_patch_risk`

**Inherited paper anchors:** `multi-agent-info-theory`, `correct-not-safe`, `redteam-apr`, `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch`, `predicatefix`, `rig`.

**Build:**

- Diff parser.
- Changed-symbol detection.
- AST diff feature extraction where available.
- Graph context extraction around changed symbols.
- SARIF before/after delta.
- Test result delta model.
- Vulnerability prior features from CWE/rule-family calibration data where available.
- Interface compatibility check.
- Behavioural drift placeholder.
- MCP Sampling integration for the adapted four-agent patch audit:
  - correctness.
  - security.
  - performance.
  - compatibility.
  - fallback path when the MCP client does not advertise Sampling.
- DryRUN prediction contract:
  - intended behaviour change
  - expected files changed
  - expected positive/negative/edge cases
  - predicted outputs and side effects
  - stated invariants and risks
- Scope and permission audit:
  - changed paths versus allowlist
  - tool calls versus workflow mode
  - network/command use versus policy
  - required run events present
  - budget and compaction events accounted for
  - missing approval or denied action handling
- Maintainability gate:
  - dependency direction
  - ownership/layering
  - duplicated logic
  - state ownership
  - side-effect isolation
- Patch-risk classifier interface.
- Patch-risk classifier feature contract:
  - AST diff: changed node kinds, edit operation, touched symbols, edit distance, generated/stub file flag.
  - SARIF delta: appeared/disappeared rules, severity changes, taint/nullness/security class.
  - graph context: two-hop callers/callees, cross-file data-flow, interface boundaries, tests exercising changed nodes.
  - test residue: regression pass/fail, generated reproduction result, PoC/PoC+ result, flaky rerun entropy.
  - vulnerability prior: CWE or rule-family prior from Vul4J/SRS-style calibration where available.
- Initial deterministic risk policy before trained classifier is available.
- Four review axes:
  - correctness
  - security
  - performance
  - compatibility
- Merge/block recommendation policy.
- Operational-review integration:
  - process-compliance verdict feeds merge/block.
  - trace-incomplete or budget-exhausted blocks auto-merge recommendation.
  - incident links appear in patch-review output.

**Dependency notes:**

- The first classifier can be a rule-based/calibration-placeholder interface.
- Do not let a bare LLM label become a patch-risk verdict.
- Blocking merge decisions based on classifier output require macro-F1 >=0.75 and ECE <=0.10 for the patch's language and rule/CWE family.
- A `safe` label is only merge-supporting when deterministic gates also pass.

**Exit criteria:**

- `run_patch_review(diff)` returns per-axis findings, evidence, uncertainty, and recommendation.
- New critical SARIF alerts, broken contracts, and failing required tests override a `safe` label.
- Out-of-scope writes, unapproved tool use, or missing telemetry override a `safe` label.
- Trace-incomplete, budget-exhausted, or process-noncompliant runs cannot receive an auto-merge recommendation.
- Structural maintainability failures can block merge even when tests pass.
- `unknown` is returned when classifier calibration is missing.
- Sampling availability, reviewer roles, fallback mode, classifier calibration family, and deterministic gate outcomes are recorded in the run record.

---

### Phase 12 - Static-Analysis Alert Repair

**Purpose:** Repair SARIF/SAST alerts using analyser evidence.

**Architecture coverage:**

- F7 static-analysis alert repair
- `run_sast_repair`
- `get_predicate_examples`
- Optional offline `evolve_static_rules`
- Private `sast-repair` template

**Inherited paper anchors:** `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair`, `codeql-rule-multiagent`, `agent-coevo`, `llm4cve`, `logiceval`.

**Build:**

- Alert binding to graph nodes.
- Rule/predicate metadata extraction.
- Developer-facing alert explanation.
- Alert classification:
  - likely true positive.
  - likely false positive.
  - unknown.
  - evidence from rule metadata, path feasibility, data-flow reachability, suppressions, and historical project evidence.
- Predicate-example retrieval interface.
- Clean corpus adapter.
- Repair prompt context builder.
- Patch generation interface.
- Suppression proposal path for confirmed false positives.
- Patch application sandbox.
- Re-run static analysis.
- SARIF delta verification.
- Build/test rerun integration.
- Remaining-risk notes when the alert disappears but root-cause behaviour is not fully verified.
- Offline rule-refinement workflow:
  - `evolve_static_rules(sarif_deltas, ruleset)`.
  - disabled during normal developer repair.
  - promotable only after demonstrating >=10 pp false-positive reduction at k=5 with zero true-positive loss.

**Dependency notes:**

- Code patches are the default output for true positives.
- Rule evolution should remain an offline workflow until quality gates exist and should not run inside ordinary SAST repair.

**Exit criteria:**

- `run_sast_repair(alert_id)` can propose a patch for a known alert fixture.
- The original alert must disappear before the alert can be considered fixed.
- New higher-severity alerts block success.
- Confirmed false positives can produce a reviewed suppression or offline rule-evolution candidate, but not an unreviewed analyser-rule mutation.

---

### Phase 13 - Bug-Resolve Workflow

**Purpose:** Build the first end-to-end issue-resolution workflow.

**Architecture coverage:**

- F5 bug-resolve
- F11 run-record, policy, budget, and monitor integration for end-to-end workflow
- Public `bug-resolve` prompt
- Private `investigate`, `repair`, `blast-radius`, and `risk-classify` templates
- `run_issue_resolution`

**Inherited paper anchors:** `agentless`, `fl-context-2026`, `specrover`, `agentic-code-reasoning`, `agent-coevo`, `issue2test`, `assertflip`, `trace-prompt`, `daira`, `pvbench`.

**Build:**

- Workflow state machine:
  - load manifest and Harness Condition Sheet
  - create run record
  - investigate
  - repair candidate generation
  - DryRUN prediction
  - deterministic gates
  - patch-risk review
  - blast-radius
  - scope/permission audit
  - operational review pre-check
  - trajectory recording
- Repair context builder.
- Unified diff generation and validation.
- Pre/postcondition draft generation interface.
  - explicit `preconditions` and `postconditions` artefacts for changed functions where the workflow can infer them.
- Issue-anchored reproduction support:
  - generate a failing reproduction test when none is provided.
  - pass-then-invert candidate tests where appropriate.
  - keep generated tests separate from production changes until they fail on the buggy version for the right reason.
  - record generated-test execution, failure reason, and flakiness/entropy metadata.
- Execution-free certificate schema:
  - definitions
  - premises
  - path claims
  - counterexample search
  - conclusion
- Test/build/SARIF/interface gate runner.
- Patch selection policy.
- Final report schema.
- Session trace and evidence-manifest writer.
- Monitor hooks:
  - loop detection between investigate/repair.
  - repeated failing gate detection.
  - context/budget hard-stop.
  - stale snapshot detection before final report.

**Dependency notes:**

- This phase must come after F2 and F6.
- The repair workflow should never present a patch as resolved if gates disagree.
- The workflow should treat a missing trace, missing permission profile, or missing verification artefact as an incomplete run.
- Operational incidents should be opened for process violations rather than hidden in the final prose report.

**Exit criteria:**

- `run_issue_resolution(issue_text)` produces:
  - ranked suspects
  - patch candidate
  - pre/postcondition draft
  - certificate
  - gate results
  - patch-risk verdict
  - blast-radius map
  - Harness Condition Sheet
  - run record / session trace reference
  - operational compliance verdict
- Failed or uncertain gates produce a non-merge recommendation.
- DryRUN/actual mismatches are reported and must be resolved or accepted as explicit residual risk.
- Process-noncompliant, trace-incomplete, or budget-exhausted runs cannot recommend merge.
- Generated reproduction tests cannot count as hard evidence until they execute, fail on the pre-fix version for the expected reason, and pass or explainably change after the candidate patch.

---

### Phase 14 - Implementation-Check Workflow

**Purpose:** Determine whether current implementation satisfies design/spec clauses.

**Architecture coverage:**

- F4 implementation-check
- F11 run-record and policy/gate evidence for implementation-check verdicts
- Public `implementation-check` prompt
- Seven-stage implementation-check DAG
- Private `audit` mode for implementation checks
- `run_implementation_check`

**Inherited paper anchors:** `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `codespecbench`, `swe-qa`, `coreqa`, `repo-path-retrieval-llm`, `swd-bench`, `agent-coevo`.

**Build:**

- Spec/document ingestion:
  - Markdown first
  - PDF/HTML later
- Clause extraction interface.
- Clause model:
  - `clause_id`
  - text
  - source span
  - scope
  - priority
  - checkability
  - target candidates
  - risk class
  - rejected interpretations
- Harness-policy clause class for requirements expressed in `AGENTS.md`, runtime overlays, tool descriptions, and release gates.
- Structured intent graph.
- Clause-to-code grounding through:
  - document links
  - repo-QA
  - graph slices
  - interface contracts
- Contract artefact generation:
  - Semgrep
  - CodeQL
  - pytest/unit tests
  - natural-language probes
  - later JML-like forms where relevant
- Static verdict runner.
- Optional dynamic verdict hook.
- Stage-7 verdict aggregator.
- Verdict rules:
  - `violated` when a hard predicate fires, a required code path is absent, an interface contract is broken, or trusted dynamic evidence contradicts the clause.
  - `satisfied` when hard predicates pass and graph/test/static or trusted dynamic evidence supports the clause with calibrated confidence.
  - `unknown` when evidence is missing, repo-QA is behaviour-tracing only, graph links are ambiguous, or dynamic evidence is unavailable for a runtime-only claim.
- Clause verdict matrix.
- Operational evidence binding:
  - clause checks record which graph snapshot, resources, tools, and gates were used.
  - stale or mixed snapshots force `unknown`.
  - missing required policy/gate evidence can produce `violated` or `unknown`.
- Manifest and tool-description regression integration for behaviour-spec clauses.

**Dependency notes:**

- Generated predicates/tests must compile or lint before they become hard evidence.
- Behaviour-tracing repo-QA should support a verdict only within measured confidence bounds.
- Behaviour-tracing repo-QA alone cannot auto-pass high-stakes checks until graph-augmented `swe-qa` / `coreqa` behaviour accuracy reaches >=70%.
- Security/privacy clauses must prefer static/data-flow evidence over natural-language answers.
- Harness policy clauses must be checked against executable traces or deterministic gate outputs whenever possible.
- Stage-7 auto-pass requires ECE <=0.10 on the Vul4J calibration set or accepted local equivalent.

**Exit criteria:**

- `run_implementation_check(spec)` returns clause-level `satisfied`, `violated`, or `unknown`.
- Ungrounded clauses are preserved as `unknown`, not dropped.
- Hard predicate failures dominate soft positive evidence.
- The stage-7 aggregator preserves calibrated confidence and ECE bucket per clause.
- Manifest, permission, and verification-policy regressions can produce `violated` even when application tests pass.
- Implementation-check reports include run record, harness condition, and operational compliance status.

---

### Phase 15 - Cross-Language and Cross-Repository Blast Radius

**Purpose:** Make impact analysis a reusable deterministic service.

**Architecture coverage:**

- F8 blast radius
- Private `blast-radius` template

**Inherited paper anchors:** `rig`, `logiclens`, `eagle-x`, `swe-polybench`, `defects4c`, `arise`.

**Build:**

- Change-set parser.
- Changed graph node detection.
- Traversal policies by change type:
  - internal implementation change
  - public API change
  - IDL/schema/contract change
  - security-sensitive change
  - generated-file change
- Impact grouping:
  - direct callers
  - downstream behaviours
  - tests
  - interfaces
  - services
  - repositories
  - static-analysis reachability
  - linked docs/specs
- Generated-stub reporting:
  - report the source contract that should change.
  - report generated files that are affected.
  - warn against manual edits to generated artefacts unless the policy explicitly allows them.
- C/C++ impact details when available:
  - ABI-relevant signatures.
  - template instantiations.
  - ownership/nullness edges.
  - build-target reachability.
- Ambiguous interface candidate bucket.
- Human-readable impact report.

**Dependency notes:**

- A basic blast-radius function is useful in Phase 13.
- This phase hardens it into a standalone feature.

**Exit criteria:**

- Given a diff, the tool reports local, test, interface, cross-repo, SAST, and documentation impact.
- Ambiguous links are separated from confirmed links.
- Generated files and ABI-sensitive C/C++ changes receive explicit impact notes.

---

### Phase 16 - Dynamic Trace Augmentation

**Purpose:** Add runtime evidence when static evidence is inconclusive.

**Architecture coverage:**

- F9 dynamic trace augmentation
- `capture_trace`

**Inherited paper anchors:** `trace-prompt`, `daira`, `tracerepair`, `inspectcoder`, `agent-coevo`.

**Build:**

- Trace run contract:
  - command
  - timeout
  - environment snapshot
  - scope filter
  - redaction policy
- Python trace adapter using `sys.settrace`, Hunter-style tracing, or project hooks.
- JS/TS trace adapter placeholder using inspector/V8 hooks where available.
- C/C++ trace/probe adapter placeholder using sanitizers, `rr`, `gdb`, or project-specific probes when a reproducible crash exists.
- Raw trace artefact store.
- Scope filtering.
- Trace compression/summarisation interface.
- State-diff and divergence-point model.
- Integration into:
  - F2 localisation
  - F4 implementation-check
  - F5 bug-resolve
  - F6 patch-review

**Dependency notes:**

- Dynamic trace capture should be fallback evidence, not default context.
- Raw traces should not be inserted wholesale into LLM context.

**Exit criteria:**

- `capture_trace(script, scope_filter)` stores raw trace and returns compressed evidence.
- Non-reproducing traces are represented as uncertainty rather than hard disproof.

---

### Phase 17 - Trajectory Memory and Experience Replay

**Purpose:** Reuse prior investigations and repairs safely.

**Architecture coverage:**

- F10 memory and replay
- F11 reviewed operational lesson promotion
- `code-intelligence://memory/{repo}/trajectories`
- `retrieve_memory`
- `record_trajectory`
- `memory_compact`
- `promote_operational_lesson`

**Inherited paper anchors:** `agent-her`, `evo-memory`, `memory-management-empirical`, `graph-memory-rl`, `c2f-grounded-memory`, `reporepair`, `predicatefix`, `schema-grounded-memory`, `ama-bench`, `agentic-harness-engineering`.

**Build:**

- Memory opt-in policy.
- Schema-grounded project-memory model:
  - decisions
  - constraints
  - allowed commands
  - components
  - incidents
  - explicit unknowns
  - rejected options
- Trajectory record schema:
  - issue
  - repo
  - FL decisions
  - graph slices
  - patch
  - SARIF delta
  - tests
  - outcome
  - utility
- Privacy and retention fields:
  - retention class.
  - expiry or review date.
  - source run.
  - owner.
  - export/delete metadata.
  - rollback path.
  - bounded snippets only by default, not raw prompts, full traces, command output, or full source files.
- Redaction and secret scanning before persistence.
- Write-path validation:
  - required fields present
  - source trace or PR linked
  - contradiction check against current records
  - data classification checked
  - review state recorded
- Coarse retrieval for investigation.
- Fine retrieval for repair and review.
- Misalignment guard:
  - reject high-similarity but historically low-utility records
- Hindsight relabelling interface.
- Eviction/retention policy:
  - promote
  - demote
  - expire
- Operational lesson promotion:
  - source run/event links.
  - reviewed trigger condition.
  - target type: memory, detector, eval, static-analysis rule, readiness task, or governance policy.
  - owner and expiry/review date.
  - rollback path.
- Memory resource.

**Dependency notes:**

- Build memory after workflows and gates exist, otherwise low-quality trajectories will be stored too early.
- Memory must never override current hard evidence.
- Do not store vague natural-language lessons as authoritative project memory; promote durable lessons into manifests, skills, tests, or schema-grounded records.

**Exit criteria:**

- Workflows can record trajectories.
- `retrieve_memory(issue_text, phase)` returns useful hints plus rejected-memory notes.
- Memory can be compacted deterministically.
- Exact project facts are retrieved through validated records, not unconstrained prose inference.
- Memory updates are reviewable and rollbackable.
- Unreviewed operational lessons remain run artefacts and are not retrieved as durable memory.
- Raw prompts, full traces, full command outputs, and full source files are not durable memory unless an explicit reviewed policy allows a narrower retained artefact.

---

### Phase 18 - Full Evaluation, Calibration, and Release Gates

**Purpose:** Move from feature-complete prototype to production-ready package.

**Architecture coverage:**

- T1-T4 benchmark ladder
- F11 operational harness gates
- RDS v0.2 logging
- Patch-risk calibration
- Implementation-check ECE gate
- Memory ship gate
- Cross-language drift checks

**Inherited paper anchors:** `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench`, `swe-bench-illusion`, `swe-qa-pro`, `livecoder`, `swe-rebench-v2`, `compass`, `pvbench`, `agent-her`, `evo-memory`, `agenttrace`, `aer`, `runtime-governance`, `tokalator`, `cqa`, `agentfixer`, `workstream`, `needle-repo`, `tdad`.

**Build:**

- T1 smoke suite:
  - small `swe-bench-live` subset or local equivalent
  - PoC+ fixtures
- T2 nightly regression:
  - repair trend
  - repo-QA file-location trend
  - manifest/tool-description regression trend
  - maintainability oracle trend
- T3 cross-language:
  - SWE-PolyBench-style fixtures
  - Defects4C-style fixtures
- T4 implementation/spec:
  - CodeSpecBench-style fixtures
  - Vul4J calibration set or local equivalent
- Calibration reports:
  - patch-risk ECE
  - implementation-check per-clause ECE
  - repo-QA thresholds
  - memory HER+eviction pass-rate delta at constant context budget
- Harness ablation reports:
  - permissions on/off or narrowed/widened
  - verification gates on/off
  - memory enabled/disabled
  - compaction policy variants
  - prompt/manifest variants
- Operational harness gates:
  - trace completeness.
  - policy compliance.
  - budget reliability.
  - maintainability oracle pass rate.
  - prompt/manifest regression pass rate.
  - readiness threshold by autonomy level.
  - P0/P1 incident closure.
- Adversarial and cumulative checks:
  - prompt/document injection
  - tool-boundary misuse
  - out-of-scope write attempt
  - multi-step policy bypass
  - reward-hackable eval-task audit
- Production-derived eval refresh workflow:
  - preserve realistic prompts
  - hide solution diffs
  - include fail-to-pass and pass-to-pass tests
  - validate test relevance
  - remove flaky tasks
- Release gate command.
- Benchmark report templates.

**Dependency notes:**

- Do not market feature readiness from single-number resolve-rate.
- Report resolve-rate conditioned on correct fault localisation.
- Report vulnerability-class pass-rate with PoC+ style validation where available.
- Memory hints are enabled by default only if HER plus eviction beats success-only memory by >=3 pp pass-rate at constant context budget on the internal T2/T3 harness.
- Hold model/runtime fixed when claiming a harness improvement.
- Benchmark tasks should be difficult, adversarial enough to expose shortcuts, and legible to human reviewers.

**Exit criteria:**

- T1-T4 run metadata is stored as eval resources.
- Release reports include Harness Condition Sheets and AI-readiness scores.
- Release reports include process-compliance rate, trace replay success rate, policy violations, budget hard stops, incident recidivism, and cost per accepted verdict.
- Release gates are reproducible from stored artefacts.
- Feature readiness is tied to measured thresholds, not subjective assessment.
- No workflow graduates to production without reliability, security, maintainability, cost, and traceability thresholds.
- A model/algorithm change cannot be accepted as an improvement if it raises resolve-rate while materially lowering operational trace replay, policy compliance, or incident performance.

---

### Phase 19 - Operational Hardening and Distribution

**Purpose:** Prepare the tool for real developer use.

**Inherited paper anchors:** `rig`, `logiclens`, `swe-bench-live`, `predicatefix`, `memory-management-empirical`, `agenttrace`, `aer`, `runtime-governance`, `cqa`, `agentfixer`, `schema-grounded-memory`.

**Build:**

- Cache invalidation hardening.
- File watcher and git hook integration.
- Performance profiling.
- Large graph chunking.
- Resource subscription recovery.
- Task TTL and authorization hardening.
- Permission profile hardening for read/search/edit/execute/review/commit modes.
- Sandbox/devcontainer templates for local and CI use.
- Session replay and incident-diagnosis tooling.
- Operational ledger retention, export, and delete tooling.
- Trace redaction audit and sampled replay checks.
- `run_operational_review` report renderer.
- `run_readiness_audit` report renderer.
- Manifest regression test runner for released prompts, skills, tool descriptions, and workflow policies.
- Cumulative risk monitoring for repeated failures, repeated tool denials, budget overrun, and suspicious multi-step patterns.
- Harness drift checks for missing, stale, relaxed, or out-of-stage manifests, skills, hooks, tool descriptions, and CI policies.
- Privacy controls:
  - redaction
  - retention classes
  - export/delete metadata
- Documentation:
  - installation
  - quickstart
  - architecture notes
  - plugin authoring guide
  - evaluation guide
  - harness setup guide
  - incident response guide
- Packaging and release automation.

**Exit criteria:**

- Tool can be installed as a Python package.
- Local MCP server can index and serve a multi-repo workspace.
- Documentation explains limitations, confidence behaviour, and release gates.
- Documentation explains the harness condition, permission profiles, telemetry, memory governance, and rollback path.
- A production release can be diagnosed from stored traces, eval artefacts, and manifest/tool versions.
- A production release can be diagnosed from run records, operational ledger entries, incidents, budget events, and policy decisions.
- Re-running the harness check is idempotent when no drift exists.

---

## 4. Recommended Milestones

### Milestone 0 - Harness Quality Baseline

**Phases:** H0-0

**Capabilities:**

- Repo-local manifests define constraints, scope, quality gates, and cost policy.
- HC1-HC6 hard constraints are present and checked for non-relaxation.
- Current harness stage (`S0`-`S3`) and next-stage controls are assessed.
- Tool permissions, sandbox policy, and path/network boundaries are explicit.
- Session telemetry and Harness Condition Sheet reporting exist from the first implementation slice.
- Local verify path covers lint, tests, secrets, dependency scanning, SAST where available, and manifest/tool-description regression tests.
- Harness drift is classified, and relaxed policies block refresh/release until reviewed.
- AI-readiness report has five per-axis scores and a no-regression check.

**Why this milestone matters:**

It prevents the project from becoming a feature-complete but unauditable LLM wrapper. Every later quality claim depends on this baseline.

---

### Milestone A - Static Evidence and Operational Runtime MVP

**Phases:** 0-4A

**Capabilities:**

- Register repositories.
- Build/update a local graph.
- Query graph slices through MCP.
- Track snapshots and provenance.
- Create run records and harness-condition sheets.
- Evaluate basic tool/path/policy decisions.
- Record budget, monitor, and incident events.
- Run operational-review and readiness-audit MVPs.

**Why this milestone matters:**

It proves the package is a static-analysis evidence system with a reviewable runtime, not only an LLM wrapper.

---

### Milestone B - Multi-Language and SARIF Foundation

**Phases:** 5-7

**Capabilities:**

- Index Python, JS/TS, and C/C++ evidence.
- Import and normalize SARIF.
- Link alerts to graph nodes.
- Traverse at least one cross-language interface.

**Why this milestone matters:**

It establishes the core product claim: cross-language and cross-repository static code analysis with auditable evidence.

---

### Milestone C - Localisation and Measurement

**Phases:** 8-10

**Capabilities:**

- Answer repo questions with cited graph evidence.
- Localize likely fault locations.
- Run smoke/regression evaluation.
- Report harness conditions and reliability deltas.
- Run ambiguity, security, and maintainability eval cases.
- Log RDS features.

**Why this milestone matters:**

It gives measurable fault-localisation quality before repair automation is introduced.

---

### Milestone D - Review and Repair Gates

**Phases:** 11-12

**Capabilities:**

- Review patches across correctness, security, performance, and compatibility.
- Audit scope, permission use, DryRUN predictions, and maintainability.
- Block process-noncompliant, trace-incomplete, or budget-exhausted runs.
- Classify patch risk through a typed interface.
- Repair SARIF alerts and verify SARIF deltas.

**Why this milestone matters:**

It builds the safety layer that every patch-producing workflow must pass.

---

### Milestone E - End-to-End Workflows

**Phases:** 13-15

**Capabilities:**

- Resolve bug reports through investigate, repair, gates, risk, and blast-radius.
- Check implementation against design/spec clauses.
- Produce cross-language impact maps.
- Include operational compliance verdicts and incident links in workflow reports.

**Why this milestone matters:**

This is the first point where the package becomes a full LLM-SCA workflow product.

---

### Milestone F - Runtime Evidence and Memory

**Phases:** 16-17

**Capabilities:**

- Capture scoped runtime traces when static evidence is inconclusive.
- Store and retrieve useful prior trajectories.
- Reject harmful or low-utility memories.

**Why this milestone matters:**

It improves ambiguous cases without weakening the evidence discipline.

---

### Milestone G - Production Readiness

**Phases:** 18-19

**Capabilities:**

- T1-T4 benchmark ladder.
- Calibration and release gates.
- Harness ablation, adversarial, and production-derived eval reports.
- Privacy and retention controls.
- Packaging, docs, and operational hardening.

**Why this milestone matters:**

It turns the prototype into a package that can be trusted in real developer workflows.

---

## 5. First Implementation Slice

The first concrete implementation slice should be intentionally small:

1. Add the harness baseline: manifests with HC1-HC6, permission profile, sandbox notes, session-trace schema, Harness Condition Sheet template, harness-stage/readiness report, drift classifier, and local verify command.
2. Create the package scaffold.
3. Implement graph/evidence schemas plus run-record, policy-decision, budget-event, monitor-alert, incident, and readiness schemas.
4. Implement repository registration.
5. Implement a local graph and operational store.
6. Implement Python file/symbol/import indexing.
7. Implement `graph_build`.
8. Implement `get_graph_slice`.
9. Expose `repos`, `schema`, `graph/slice`, `schema/run-record`, and minimal `runs/{run_id}` resources through MCP.
10. Implement `record_run_event`, `record_harness_condition`, and a minimal `evaluate_tool_policy`.
11. Add fixture tests, one manifest/tool-description regression test, and one non-relaxation mutation test.

This slice avoids repair, LLM calls, embeddings, patch generation, and dynamic tracing. It produces the core substrate that every later feature needs.

---

## 6. Early Non-Goals

The following should not be built in the first slice:

- Automatic patch generation.
- Full implementation-check DAG.
- Trained patch-risk classifier.
- Trajectory memory.
- Dynamic tracing.
- Full benchmark integration.
- All interface plugins.
- CodeQL rule evolution.
- Governed self-evolution of prompts, manifests, tools, or release gates.
- Automatic memory promotion without review.
- Full incident-management UI or dashboard.
- Advanced cumulative-risk detection beyond deterministic first-pass monitors.
- Automatic readiness remediation PRs.
- Broad auto-execute or bypass-permissions modes.

These depend on evidence quality, SARIF integration, graph traversal, and evaluation plumbing.

---

## 7. Main Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Harness controls arrive after feature work | Feature demos become unauditable and hard to calibrate | Start with Phase H0; require telemetry, permission profile, and Harness Condition Sheet for phase acceptance |
| Local agents developing the package bypass the same harness rules the product will enforce | The implementation process creates low-quality, unauditable code before product controls exist | Use the Local-Agent Development Contract from §1.3 from day one; require `.agent/plan.md`, verify evidence, drift checks, and readiness no-regression for implementation PRs |
| Graph schema becomes too broad too early | Slow implementation and unstable APIs | Start with required node/edge core, version schema, add capability flags |
| Language backends produce inconsistent facts | Low trust in graph traversal | Preserve provenance/confidence and cross-check facts where possible |
| LLM outputs bypass gates | Unsafe or unauditable verdicts | Enforce typed evidence contracts and hard-gate precedence |
| Tool or MCP permissions are too broad | Accidental side effects, data leakage, or hidden network dependency | Use tool DAG, deny-first modes, path/network allowlists, and scope audits |
| Prompt or manifest changes silently regress behaviour | Workflow quality changes without code changes | Treat prompts, manifests, skills, and tool descriptions as tested artefacts |
| Run records are incomplete or too noisy | Operational review cannot reconstruct causality or reviewers ignore trace output | Use typed event schemas, required event coverage, artefact hashes, redaction, and trace-completeness gates |
| Policy engine diverges from workflow reality | Allowed/denied decisions become either unsafe or too restrictive | Bind every tool to a stage, side-effect class, path/network scope, and test with policy fixtures |
| Budget/compaction hides key evidence | Workflow returns confident answers after losing context | Log compaction, link full artefacts, force `unknown` or checkpoint when required evidence is removed |
| Incidents do not feed improvement | The same operational failures recur | Require detector/eval/policy/memory follow-up and track incident recidivism |
| SARIF binding is imprecise | Weak SAST repair and patch-risk signals | Store alert locations even when symbol binding fails; expose uncertainty |
| Interface links are ambiguous | False blast-radius reports | Separate confirmed and candidate links |
| Evaluation arrives too late | No way to know whether features work | Build smoke evaluation before repair workflows |
| Tests pass while structure degrades | Working patches make the codebase harder to evolve | Add maintainability oracles for dependency direction, ownership, reuse, and side-effect boundaries |
| Benchmarks reward shortcuts | Inflated quality claims and fragile production behaviour | Use hidden tests, task audits, repeated trials, flaky-test filtering, and harness condition reporting |
| Memory stores bad trajectories | Error propagation | Make memory opt-in and implement utility filtering before default retrieval |
| Memory becomes ungoverned prose | Stale or injected memory overrides current evidence | Use schema-grounded records, source links, contradiction checks, expiry, and reviewable promotion |

---

## 8. Suggested Phase Grouping for Development Tickets

Use the following grouping when breaking work into issues:

1. **Harness and governance**
   - `AGENTS.md`, runtime overlays, `.agent/plan.md`, and skill templates
   - permission profiles and tool DAG
   - sandbox/devcontainer policy
   - session telemetry schema
   - run-record schema and writer
   - Harness Condition Sheet
   - policy evaluator and tool-stage metadata
   - budget manager and monitor detectors
   - operational-review workflow
   - readiness-audit workflow
   - harness-stage assessor
   - manifest-state resource
   - incident and promotion workflows
   - local verify command
   - manifest/tool-description regression tests
   - AI-readiness score
   - drift classifier and readiness no-regression check
   - validate-harness-controls command/gate

2. **Schemas and storage**
   - graph schema
   - evidence schema
   - verdict schema
   - trace and harness-condition schemas
   - run-event, policy-decision, budget-event, monitor-alert, incident, and promotion schemas
   - repository registry
   - graph store
   - operational ledger store

3. **Indexing**
   - file tree scanner
   - git snapshot model
   - ctags adapter
   - tree-sitter adapter
   - language-specific call graph adapters
   - symbol-summary cache and summary resource backing store
   - git blame-chain collector and blame resource backing store
   - embedding/vector cache invalidated by snapshot
   - incremental update

4. **MCP**
   - resource router
   - tool router
   - task manager
   - notifications
   - resource subscriptions and list-changed notifications
   - Sampling capability negotiation and fallback
   - prompt registry

5. **Static analysis**
   - SARIF parser
   - Semgrep adapter
   - Bandit adapter
   - CodeQL adapter
   - optional external SARIF import adapters
   - SARIF-to-graph binding
   - SARIF delta
   - predicate-example retrieval
   - offline rule evolution

6. **Interfaces**
   - plugin contract
   - plugin reload
   - HTTP-REST plugin
   - WebSocket plugin
   - omniORB-IDL plugin
   - future plugin backlog: gRPC, Protobuf, ZeroMQ, MQTT, DBUS
   - cross-language traversal

7. **Analysis workflows**
   - repo-QA
   - fault localisation
   - patch review
   - SAST repair
   - bug resolve
   - implementation check
   - blast radius
   - private workflow templates: investigate, repair, audit, blast-radius, sast-repair, risk-classify, evaluate

8. **Evidence extensions**
   - dynamic traces
   - trajectory memory
   - embeddings
   - risk classifier
   - calibration
   - reproduction-test generation and pass-then-invert checks

9. **Evaluation and release**
   - T1 smoke
   - T2 regression
   - T3 cross-language
   - T4 implementation/spec
   - RDS logging
   - reliability surface and repeated trials
   - harness ablations
   - production-derived eval refresh
   - trace-completeness and process-compliance gates
   - budget reliability and incident recidivism metrics
   - release gate command

---

## 9. Implementation Order Summary

The recommended order is:

```text
H0. Harness quality foundation (starts first and stays active)
0. Package skeleton
1. Schemas and evidence model
2. Graph store and repo registry
3. Repository indexing MVP
4. MCP server core
4A. Operational harness runtime plane
5. Multi-language backends
6. SARIF/static analysis
7. Cross-language plugins
8. Repo-QA
9. Fault localisation
10. Evaluation baseline
11. Patch review and risk gates
12. SAST alert repair
13. Bug-resolve
14. Implementation-check
15. Blast radius hardening
16. Dynamic traces
17. Trajectory memory
18. Full evaluation and calibration
19. Operational hardening and distribution
```

This order keeps the project aligned with the architecture's core rule: deterministic, typed, versioned evidence first; LLM/ML reasoning second; user-facing automation only after gates and evaluation exist. The harness layer makes that rule enforceable by requiring policy, permissions, telemetry, verification, and evaluation evidence for every release claim.

---

## 10. Citation Registry Use

This implementation plan intentionally keeps citation anchors, not full bibliography entries, beside implementation work. The authoritative citation metadata is inherited from `llm-sca-tooling-architecture.md` §6.1.

Harness-engineering anchors are drawn from the two local harness references listed in the header and are now represented in the architecture's citation registry. Use the architecture anchors such as `agenttrace`, `aer`, `opendev`, `runtime-governance`, `tokalator`, `cqa`, `agentfixer`, `workstream`, `needle-repo`, `tdad`, `schema-grounded-memory`, and `agentic-harness-engineering` in issues, ADRs, and release reports.

When creating follow-on implementation artefacts:

1. Use the phase-level anchors above in issue descriptions, ADRs, benchmark reports, and design notes.
2. Resolve full paper metadata from `llm-sca-tooling-architecture.md` §6.1 before external publication.
3. Resolve full harness-paper metadata from the two harness-engineering reference documents before external publication.
4. Keep source-code comments citation-light unless a comment documents a non-obvious algorithmic choice.
5. Keep end-user reports focused on evidence, harness condition, verdict, risk, and next action; include paper provenance only when the user asks for technical provenance.
