# LLM-SCA Tooling Phase 19 Implementation Plan: Operational Hardening and Distribution

> Date: 2026-05-09
> Repository name: `evidence-sca`
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 19 - Operational Hardening and Distribution
> Primary objective: prepare the tool for real developer use — cache invalidation hardening, file watcher and git hook integration, large graph chunking, Streamable HTTP transport, permission profile hardening, sandbox/devcontainer templates, session replay, incident-diagnosis tooling, privacy controls, packaging and release automation, and documentation covering installation, quickstart, architecture, plugin authoring, evaluation, harness setup, and incident response.

---

## 1. Phase Summary

Phase 19 is the distribution and operational hardening phase of `evidence-sca`. Phases 1-18 built and validated the complete feature set against production-grade thresholds. Phase 19 makes the tool installable, configurable, diagnosable, and maintainable by real developers who were not involved in building it.

The central rule for this phase is:

```text
A production release can be diagnosed from run records, operational ledger
entries, incidents, budget events, and policy decisions alone — without access
to session transcripts or source code of the analysed repository.
Re-running the harness check is idempotent when no drift exists.
Documentation explains limitations and confidence behaviour, not just features.
The tool can be installed as a Python package without knowing the internals.
```

Phase 19 should implement:

- Cache invalidation hardening.
- File watcher and git hook integration.
- Performance profiling and large graph chunking.
- Resource subscription recovery after disconnect.
- Task TTL and authorization hardening.
- Permission profile hardening for all six modes.
- Sandbox/devcontainer templates.
- Session replay and incident-diagnosis tooling.
- Operational ledger retention, export, and delete tooling.
- Trace redaction audit and sampled replay checks.
- Manifest regression test runner for released prompts, skills, and tool descriptions.
- Cumulative risk monitoring.
- Harness drift checks for manifests, skills, hooks, and CI policies.
- Privacy controls: redaction, retention classes, export/delete metadata.
- Streamable HTTP transport (alongside existing stdio).
- Packaging and release automation.
- Documentation (seven guides).

### Architecture Coverage

Phase 19 covers:

- F11 operational harness hardening and continuous improvement.
- H8 diagnosis and rollback harness control.
- H10 governed harness evolution.
- `run_operational_review` and `run_readiness_audit` report renderers (Phase 4A/18 launchers + Phase 19 rendering).
- `code-intelligence://governance/{repo}/manifest-state` resource hardening.
- `code-intelligence://incidents/{incident_id}` resource hardening.
- File watcher and git hook integration for `graph_update`.
- Streamable HTTP transport (Phase 4 was stdio-only per tech stack §10.2).

### Inherited Paper Anchors

Use these anchors in Phase 19 issues, ADRs, and operational notes:

- `rig`
- `logiclens`
- `swe-bench-live`
- `predicatefix`
- `memory-management-empirical`
- `agenttrace`
- `aer`
- `runtime-governance`
- `cqa`
- `agentfixer`
- `schema-grounded-memory`

## Technology Stack

This phase uses the following libraries from `llm-sca-tooling-tech-stack.md`:

| Library/Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Python | — | 3.12+ | Runtime |
| uv | — | latest | Environment and dependency management; `uv build`, `uv publish` for release automation |
| watchdog | `watchdog` | >=4.0 | File system event monitoring for `graph_update` auto-trigger; cross-platform file watcher |
| Pydantic v2 | `pydantic` | >=2.0 | `PermissionProfile`, `DevcontainerConfig`, `CumulativeRiskEvent`, `HarnessDriftRecord`, `RetentionPolicy` schemas; `extra="forbid"` |
| SQLModel + Alembic | `sqlmodel`, `alembic` | >=0.0.21, >=1.13 | Ledger retention tables, export/delete audit trail; new tables require migrations |
| orjson | `orjson` | >=3.10 | Session replay JSONL, ledger export, diagnostic report JSON I/O |
| FastMCP + FastAPI + uvicorn | `fastmcp`, `fastapi`, `uvicorn` | >=2.0, >=0.115, >=0.30 | Streamable HTTP transport alongside stdio; `uvicorn` as ASGI server for HTTP mode |
| Typer + Rich | `typer`, `rich` | >=0.12, >=13.0 | CLI install, quickstart, replay, and diagnosis commands; Rich for structured terminal output |
| pytest + pytest-asyncio | `pytest`, `pytest-asyncio` | >=8.0, >=0.23 | Phase 19 hardening and distribution tests; `asyncio_mode="auto"` |
| hatch | `hatch` | >=1.12 | Packaging and distribution; `hatch build` for wheel and sdist; `hatch publish` for PyPI |

- `watchdog` is introduced in this phase for file system monitoring. All file-watch event handlers are dispatched via asyncio; blocking OS calls use `loop.run_in_executor`.
- Streamable HTTP transport uses uvicorn (already a production dependency from Phase 4) alongside the existing stdio transport. The same FastMCP server handles both transports based on startup configuration.
- `hatch` is the packaging tool; it generates the wheel and sdist from `pyproject.toml`. Release automation uses `hatch build && hatch publish` (gated by the Phase 18 release gate command).
- Rich is used in this phase for the CLI diagnosis and replay commands; the scope constraint (CLI layer only) from the tech stack remains enforced.
- All async conventions from the tech stack (§15) apply without exception in Phase 19.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 19 depends on all preceding phases, specifically:

- Phase 4 MCP server core: resource routing, tool registry, task manager, notification infrastructure.
- Phase 4A operational harness: run records, incident workflow, ledger store, policy engine.
- Phase 10 eval harness: T1-T4 eval artefacts, `HarnessConditionSheet`.
- Phase 18 release gates: release gate command, calibration reports, benchmark report templates.
- All documented MCP tools, resources, and prompts from Phases 1-18.

### Phase Outputs

Phase 19 should produce:

- `CacheInvalidationHardener` module.
- `FileWatcherService` with `watchdog` integration.
- `GitHookInstaller` for post-commit and post-checkout hooks.
- `GraphChunker` for large-graph lazy loading.
- `SubscriptionRecoveryManager`.
- `TaskAuthorizationHardener`.
- `PermissionProfileSet` with all six mode definitions.
- Devcontainer and sandbox templates.
- `SessionReplayTool` CLI command.
- `IncidentDiagnosisTool` CLI command.
- `LedgerRetentionPolicy` model and enforcement.
- `LedgerExporter` and `LedgerDeleteTool`.
- `TraceRedactionAuditor`.
- `ManifestRegressionRunner` for released artefacts.
- `CumulativeRiskMonitor`.
- `HarnessDriftChecker`.
- `RetentionPolicy` model and privacy control pipeline.
- Streamable HTTP transport configuration and startup mode.
- Python package wheel and sdist via `hatch build`.
- Release automation script.
- Seven documentation guides.
- Phase 19 tests.

### Non-Goals

Do not implement these in Phase 19:

- Multi-tenancy or enterprise authentication (these require a separate security design).
- Managed cloud deployment (beyond devcontainer/self-hosted documentation).
- Automatic readiness remediation PRs.
- Governed self-evolution of prompts, tools, or release gates.
- Full incident management UI or dashboard.
- Advanced reinforcement learning over operational lessons.

---

## 3. Recommended File Layout

```text
src/evidence_sca/
  hardening/
    __init__.py
    cache_invalidation.py
    file_watcher.py
    git_hooks.py
    graph_chunker.py
    subscription_recovery.py
    task_authorization.py
    permission_profiles.py
    cumulative_risk.py
    harness_drift.py
    trace_redaction_audit.py
    manifest_regression_runner.py

  operations/
    ledger_retention.py
    ledger_exporter.py
    ledger_delete.py

  privacy/
    __init__.py
    retention_policy.py
    redaction.py
    export_delete.py

  cli/
    replay.py
    diagnose.py
    release.py

  transport/
    http_transport.py

docs/
  installation.md
  quickstart.md
  architecture.md
  plugin-authoring-guide.md
  evaluation-guide.md
  harness-setup-guide.md
  incident-response-guide.md

.devcontainer/
  devcontainer.json
  Dockerfile

tests/
  hardening/
    test_cache_invalidation.py
    test_file_watcher.py
    test_git_hooks.py
    test_graph_chunker.py
    test_subscription_recovery.py
    test_task_authorization.py
    test_permission_profiles.py
    test_cumulative_risk.py
    test_harness_drift.py
    test_trace_redaction_audit.py
    test_manifest_regression_runner.py
  operations/
    test_ledger_retention.py
    test_ledger_exporter.py
  privacy/
    test_retention_policy.py
    test_redaction_pipeline.py
  cli/
    test_replay.py
    test_diagnose.py
    test_release_cmd.py
  transport/
    test_http_transport.py
```

---

## 4. Cache Invalidation Hardening

### 4.1 Problem

Stale cache entries (graph subgraphs, symbol summaries, embeddings, SARIF bindings) can silently produce incorrect evidence if invalidation logic has gaps.

### 4.2 Hardening Requirements

Rules:

- Every cached entry must carry a `(repo_id, git_sha)` key. A cache hit is only valid when the current graph's `git_sha` matches the cache key's `git_sha`.
- On `graph_update` completion, emit a cache-invalidation event for all affected file paths.
- On dirty-worktree snapshot advance, invalidate all summaries and embeddings for the changed files.
- A graph query that hits a stale cache entry must return a `stale_cache` diagnostic, not a silent old result.
- The embedding cache (Phase 9) must be invalidated before fault localisation uses it if the relevant file has changed.

### 4.3 `CacheInvalidationHardener` Module

Responsibilities:

- Subscribe to `graph_update` completion notifications.
- Compute the set of affected cache keys from the changed file paths.
- Invalidate (delete or mark stale) all affected entries.
- Record invalidation events in the operational ledger.
- Expose a `verify_cache_consistency(repo_id)` diagnostic command.

---

## 5. File Watcher and Git Hook Integration

### 5.1 `FileWatcherService`

Uses `watchdog` to monitor registered repo directories for file system changes. On detecting relevant changes:

1. Debounce events with a configurable window (default 2 seconds).
2. Collect changed file paths.
3. Trigger `graph_update` via the Phase 4 task manager.
4. Emit `notifications/resources/updated` when the update completes.

### 5.2 `watchdog` Integration

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RepoChangeHandler(FileSystemEventHandler):
    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule_update(event.src_path)
```

Rules:

- File watcher runs as a background asyncio task; `watchdog` events are dispatched via `loop.call_soon_threadsafe`.
- File watcher only activates when `workspace.file_watcher_enabled: true` in config.
- `.git/` directory changes are excluded from the watch scope.

### 5.3 Git Hook Installer

`GitHookInstaller` installs `post-commit` and `post-checkout` git hooks in registered repos:

- `post-commit`: calls `evidence-sca graph-update --repo .` after each commit.
- `post-checkout`: calls `evidence-sca graph-update --repo .` after branch switch.

Rules:

- Hook installation requires execute-mode permission.
- Hook installer records the installation in the operational ledger.
- Hook uninstallation must remove the hook completely; partial uninstallation is a diagnostic.

---

## 6. Performance Profiling and Large Graph Chunking

### 6.1 Performance Profiling

Phase 19 adds performance profiling to identify bottlenecks before production:

- Profile `graph_build` and `graph_update` for repos with >10,000 files.
- Profile `get_graph_slice` for slices with >500 nodes.
- Profile `run_eval_suite` T2 run for wall-clock time vs. token budget.
- Results stored as operational events; visible in `run_operational_review`.

### 6.2 `GraphChunker`

Large graphs are lazily chunked to prevent memory exhaustion and resource response overflow.

`GraphChunker` responsibilities:

- Split a graph manifest into N chunks of at most `max_chunk_nodes` nodes.
- Store chunk artefacts in the Phase 2 artefact registry.
- Serve chunks on demand when a resource read requests a specific chunk.
- Support chunk streaming for `get_graph_slice` when the slice spans multiple chunks.

Rules:

- Default `max_chunk_nodes: 2000`.
- Chunk boundaries follow module/package topology, not arbitrary line cuts.
- A graph resource read always returns a manifest + chunk references, never the full graph inline.
- Large resource payloads always trigger artefact reference, not inline JSON.

---

## 7. Resource Subscription Recovery

### 7.1 Problem

MCP clients that disconnect and reconnect may miss resource update notifications. Without recovery, they hold stale cached resource states.

### 7.2 `SubscriptionRecoveryManager`

Responsibilities:

- Track the last notification timestamp per subscribed resource per client.
- On reconnect: send all missed `notifications/resources/updated` events since the last received notification.
- If the client's last received notification is older than the event log retention window: send a `notifications/resources/list_changed` to force full re-sync.
- Missed notifications are recoverable from the operational ledger, not reconstructed from memory.

### 7.3 Rules

Rules:

- Subscription state is persisted in the Phase 2 operational store.
- On server restart: recover subscription state from the store.
- Subscription state is scoped to authorization context where the transport supports it.

---

## 8. Task TTL and Authorization Hardening

### 8.1 Task TTL Hardening

Phase 4 introduced task TTL. Phase 19 hardens it:

- Expired tasks are pruned from the task store on a configurable schedule (default: hourly).
- Expired task artefacts are scrubbed from the artefact registry unless retained by policy.
- TTL hard-cap enforced: no task can have TTL > `workspace.max_task_ttl_seconds`.
- Restart recovery re-evaluates TTL; tasks that expired during downtime are immediately expired on restart.

### 8.2 Authorization Hardening

Rules:

- Task IDs are bound to the authorization context of the request that created them.
- Task state and result artefacts are not accessible to a different authorization context without an explicit sharing policy.
- In unauthenticated single-user mode: all tasks visible to all requests (by policy, not by default).
- In unauthenticated multi-user mode: `tasks/list` disabled; task IDs are the only access token.
- Authorization context hash is stored in `TaskRecord.authorization_context_hash` and checked on every `tasks/get` and `tasks/result` call.

---

## 9. Permission Profile Hardening

### 9.1 Six Permission Modes

Phase 19 hardens all six permission modes from Phase 4/4A:

| Mode | Read | Search | Edit | Execute | Review | Commit |
|---|---|---|---|---|---|---|
| `read_only` | ✓ | — | — | — | — | — |
| `read_search` | ✓ | ✓ | — | — | — | — |
| `read_search_edit` | ✓ | ✓ | ✓ | — | — | — |
| `read_search_execute` | ✓ | ✓ | — | ✓ | — | — |
| `review` | ✓ | ✓ | — | — | ✓ | — |
| `commit` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### 9.2 `PermissionProfileSet`

A typed model for the workspace's active permission profiles:

```text
PermissionProfileSet
  default_mode
  per_repo_overrides
  per_workflow_overrides
  network_policy
  path_allowlist
  execute_allowlist
  review_allowlist
  commit_allowlist
```

Rules:

- The active permission profile must appear in every `HarnessConditionSheet`.
- Profile changes are recorded in the governance ledger.
- A profile that widens permissions beyond the default triggers a harness drift `relaxed` finding.

---

## 10. Sandbox and Devcontainer Templates

### 10.1 Devcontainer Template

The `.devcontainer/devcontainer.json` template provides:

- Base image: Python 3.12 with `uv` pre-installed.
- Pre-installed: `universal-ctags`, `semgrep`, `git`.
- Mounted workspace at `/workspace`.
- Pre-configured `EVIDENCE_SCA_WORKSPACE=/workspace/.evidence-sca`.
- MCP server startup command in `postStartCommand`.
- HC2 default path allowlist configured for `/workspace` only.

### 10.2 CI Sandbox Template

A GitHub Actions workflow template (`.github/workflows/evidence-sca-ci.yml`) that:

- Installs dependencies via `uv sync`.
- Runs `evidence-sca graph-build` on the target repo.
- Runs `evidence-sca validate-harness-controls` and fails CI if drift found.
- Runs T1 smoke eval in null mode.
- Runs `evidence-sca release-gate --suite t1 --operational-gate-required`.

### 10.3 Rules

Rules:

- Devcontainer and CI templates must work without modification for a minimal Python repo.
- All templates document the required `EVIDENCE_SCA_*` environment variables.
- Templates must not hardcode credentials or paths outside `/workspace`.

---

## 11. Session Replay and Incident-Diagnosis Tooling

### 11.1 Session Replay CLI Command

```text
evidence-sca replay <run_id>
  --show-events
  --filter-stage <stage>
  --filter-type <event_type>
  --diff-run <other_run_id>
  --output-format <rich|json>
```

Replay responsibilities:

- Read `RunRecord` and `RunEvent` list from Phase 2 operational store.
- Reconstruct the event sequence in chronological order.
- Display tool calls, gate results, budget events, policy decisions, and monitor alerts.
- When `--diff-run` is provided: show side-by-side comparison (uses Phase 4A `compare_run_traces`).

### 11.2 Incident Diagnosis CLI Command

```text
evidence-sca diagnose <incident_id>
  --trace-run
  --show-promotion-candidates
  --output-format <rich|json>
```

Diagnosis responsibilities:

- Read the incident record from Phase 4A incident store.
- Display: impact, timeline, root cause, containment, remediation, evidence links, detector follow-up, reviewer closure.
- List all run events linked to the incident.
- If `--trace-run`: invoke replay for the linked run.
- List promotion candidates from the incident.

### 11.3 Rules

Rules:

- Replay and diagnosis commands must work from the operational store alone; they must not require access to the original source repository.
- Replay output must be deterministic for the same run record.
- Sensitive fields are redacted per the run's `redaction_policy`.

---

## 12. Operational Ledger Retention, Export, and Delete

### 12.1 `LedgerRetentionPolicy` Model

Required fields:

```text
LedgerRetentionPolicy
  workspace_id
  run_record_retention_days
  incident_retention_days
  budget_event_retention_days
  monitor_alert_retention_days
  promotion_record_retention_days
  eval_run_retention_days
  artefact_retention_days
  export_on_delete
  delete_requires_approval
```

### 12.2 `LedgerExporter`

Exports ledger records to a portable JSONL archive:

- Export scope: configurable by date range, repo, workflow type, or incident ID.
- Output: compressed JSONL with one record per line.
- Includes: run records, run events, incidents, budget events, policy decisions.
- Excludes by default: raw trace artefacts, source file content, plaintext credentials.

### 12.3 `LedgerDeleteTool`

Executes retention-policy-compliant deletion:

- Deletes records past their retention window.
- When `export_on_delete: true`: exports before deletion.
- Deletion requires approval if `delete_requires_approval: true`.
- Deletion audit trail: records what was deleted and when, without retaining the deleted content.

---

## 13. Trace Redaction Audit and Sampled Replay Checks

### 13.1 Trace Redaction Audit

Verifies that the redaction policy was applied correctly to stored run events and trace artefacts:

- Scan all string fields in a sample of run events for HC1 secret patterns.
- Report any field that matches but was not redacted.
- Audit result stored as an operational event.
- Failing audit produces a P1 incident.

### 13.2 Sampled Replay Checks

Periodically replays a random sample of completed run records and verifies:

- All referenced artefact IDs are resolvable.
- All gate events are present in the expected sequence.
- Run record is reproducible: same inputs produce the same evidence summary.

Rules:

- Sampled replay runs as a background task (not user-triggered by default).
- Failures produce `trace_replay_failure` monitor events.
- Failure rate feeds the Phase 18 `trace_replay_success_rate` operational gate metric.

---

## 14. Manifest Regression Test Runner for Released Artefacts

### 14.1 Purpose

Prompt text, tool descriptions, `AGENTS.md`, `SKILL.md` templates, and workflow policy are released artefacts that can silently regress behaviour. Phase 19 provides a runner that tests all released artefacts on every release.

### 14.2 `ManifestRegressionRunner`

Responsibilities:

- Load all registered prompts, tool descriptors, and manifest files.
- Run the Phase 10 manifest regression adapter against them.
- Compare against the previous release's stored snapshots.
- Report: visible behaviour cases, hidden policy cases, tool-order cases, semantic mutation cases, spec-evolution cases.
- Any `breaking` or `policy-relevant` classification blocks the release gate.

### 14.3 Integration with Release Gate

The release gate command (`evidence-sca release-gate`) calls `ManifestRegressionRunner` automatically. A regression finding is a blocking gate failure.

---

## 15. Cumulative Risk Monitoring

### 15.1 Purpose

Individual operations may be policy-compliant, but a sequence of them can combine into a policy violation. Phase 19 implements the cumulative-risk monitor that Phase 4A defined as a placeholder.

### 15.2 `CumulativeRiskEvent` Model

Required fields:

```text
CumulativeRiskEvent
  event_id
  run_id
  pattern_type
  contributing_events
  risk_score
  threshold_exceeded
  action_taken
  ts
```

`pattern_type` values:

- `repeated_identical_tool_calls`: same tool called >N times with identical args.
- `repeated_failing_gate_no_change`: same gate fails >N times with no evidence change.
- `context_growth_no_evidence`: context tokens grow without new graph/test/SARIF evidence added.
- `denied_operation_storm`: >M denied operations in a single session.
- `budget_exhaustion_pattern`: successive budget hard-stops across runs.
- `suspicious_multistep`: individually allowed operations that, combined, achieve a denied operation.

### 15.3 Rules

Rules:

- Cumulative risk monitor runs after each tool call in a long-running workflow.
- When `threshold_exceeded: true`: emit monitor event, optionally pause workflow for review.
- Cumulative risk events appear in `detect_run_anomalies` output.
- The `suspicious_multistep` pattern requires Phase 4A's policy engine for tracking cross-call state.

---

## 16. Harness Drift Checks

### 16.1 Purpose

Manifest artefacts (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, skill files, tool descriptions, CI policy) can become stale, weakened, or out of stage. Phase 19 hardens the drift checker from Phase 4A into a CLI command and CI gate.

### 16.2 `HarnessDriftChecker`

Checks each artefact and classifies it as:

- `clean`: present, current, non-relaxing, appropriate for current stage.
- `stale`: present but content does not reflect current tool/policy set.
- `missing`: required for current stage but absent.
- `relaxed`: present but weakens a hard constraint (HC1-HC6).
- `out-of-stage`: present but contains controls not yet appropriate for the current stage.

### 16.3 CLI Integration

```text
evidence-sca check-drift <repo>
  --stage <S0|S1|S2|S3>
  --fail-on <missing|stale|relaxed|out-of-stage|any>
  --report-out <path>
```

Rules:

- `relaxed` drift always fails CI unless a reviewed waiver is present.
- Waiver must include: reason, owner, expiry date, and rollback path.
- Drift check is idempotent: running it multiple times without changes produces the same result.

---

## 17. Privacy Controls

### 17.1 `RetentionPolicy` Model

Required fields:

```text
RetentionPolicy
  workspace_id
  data_classes
  redaction_rules
  retention_windows
  export_on_delete
  delete_requires_approval
  pii_detection_enabled
  secret_scan_enabled
  opt_out_categories
```

### 17.2 Privacy Control Pipeline

1. **Redaction at write time**: applied before any run event, trace, or trajectory is stored.
2. **PII detection**: scan string fields for PII patterns (email, name, phone) and redact.
3. **Secret scan**: HC1 secret scanner applied to all string fields before persistence.
4. **Retention class enforcement**: records past their retention window are flagged for deletion.
5. **Export on delete**: configurable; when enabled, records are exported to archive before deletion.
6. **Delete audit trail**: maintains a record of what was deleted without retaining deleted content.

### 17.3 Right-to-Delete Path

Rules:

- A user can request deletion of all records associated with their workspace.
- Deletion is processed within one business day.
- Deletion audit trail is retained for 30 days minimum.
- Deletion does not affect shared artefacts that are part of eval suites (only workspace-private records are deleted).

---

## 18. Streamable HTTP Transport

### 18.1 Purpose

Phase 4 implemented stdio transport only (per tech stack §10.2). Phase 19 adds Streamable HTTP transport for multi-client and remote deployment.

### 18.2 `HTTPTransportConfig` Model

Required fields:

```text
HTTPTransportConfig
  host
  port
  tls_enabled
  tls_cert_path
  tls_key_path
  cors_allowed_origins
  auth_token_env_var
  rate_limit_requests_per_minute
  max_connections
```

### 18.3 Startup Modes

The MCP server starts in one of two transport modes:

```text
# stdio (default, Phase 4 behavior)
evidence-sca mcp serve --transport stdio

# Streamable HTTP (Phase 19)
evidence-sca mcp serve --transport http --host 127.0.0.1 --port 8080
```

Both modes use the same `FastMCP` server instance. The transport is the only difference.

### 18.4 Security Rules for HTTP Transport

Rules:

- TLS is required for non-localhost deployments.
- Auth token required when `single_user: false`.
- Rate limiting enforced per auth context.
- HC5 (deny-by-default network egress) applies to tool execution even when the server itself is running over HTTP.
- CORS allowed origins list must be explicitly configured; wildcard `*` is rejected.

---

## 19. Packaging and Release Automation

### 19.1 `hatch` Configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/evidence_sca"]

[tool.hatch.build.targets.sdist]
include = ["src/", "tests/", "schemas/", "docs/"]
exclude = [".devcontainer/", "*.jsonl"]
```

### 19.2 Release Automation Script

```text
evidence-sca release-gate --suite all --fail-on-any     # must pass
uv run isort . && uv run black . && uv run ruff check .  # format/lint
uv run mypy src/                                          # type check
uv run pytest -x --tb=short                               # full test suite
hatch build                                               # wheel + sdist
hatch publish                                             # PyPI upload (with token)
```

### 19.3 Rules

Rules:

- Release automation must fail if the Phase 18 release gate command exits with code 1.
- PyPI upload requires a release token stored in `HATCH_INDEX_AUTH` (never hardcoded — HC1).
- Every release produces: wheel, sdist, CHANGELOG entry, and a `ReleaseGateResult` artefact stored in the workspace.
- Semantic versioning: `MAJOR.MINOR.PATCH`. Breaking MCP surface changes bump MAJOR.

### 19.4 Supply-Chain Provenance

After each release:

- Record the release wheel hash in the Phase H0 supply-chain provenance ledger.
- Record the exact `uv.lock` snapshot at release time.
- Record the MCP server version, tool set hash, and prompt revision in the release `HarnessConditionSheet`.

---

## 20. Documentation (Seven Guides)

### 20.1 `installation.md`

Covers:

- Prerequisites: Python 3.12+, `uv`, `universal-ctags`, `semgrep`.
- Installation via `uv add evidence-sca` or `pip install evidence-sca`.
- Initial configuration: `evidence-sca init --workspace .evidence-sca`.
- MCP server startup: `evidence-sca mcp serve`.
- Devcontainer quick-start: open in VS Code with devcontainer support.

### 20.2 `quickstart.md`

Covers:

- Register a repo: `evidence-sca register-repo .`.
- Build the graph: `evidence-sca graph-build`.
- Query graph slice via MCP.
- Run the bug-resolve workflow: `evidence-sca run-issue-resolution "issue text"`.
- View the report: `evidence-sca show-report <run_id>`.

### 20.3 `architecture.md`

Covers:

- Five product surfaces: MCP server, workflow orchestrator, evaluation harness, operational harness plane, operational guardrails.
- Evidence hierarchy: parser > analyser > heuristic > unknown.
- Phase dependency map (summarized from master plan).
- Key design constraints: typed evidence first, LLM reasoning second.
- How to read a `HarnessConditionSheet`.

### 20.4 `plugin-authoring-guide.md`

Covers:

- Phase 7 `InterfacePluginBase` four-method contract: `detect`, `index`, `link`, `traverse`.
- `InterfaceRecord` and `InterfaceOperation` schemas.
- `GeneratedArtifactRecord` for generated file tracking.
- Testing a plugin with the null corpus adapter.
- Registering a plugin with `plugin_reload`.
- Performance considerations: hub dampening, confidence levels.

### 20.5 `evaluation-guide.md`

Covers:

- T1-T4 benchmark ladder overview.
- Running a smoke eval: `evidence-sca run-eval-suite --suite t1 --null-mode`.
- Interpreting calibration reports.
- Adding local smoke fixtures.
- Mandatory reporting rules (eight rules from Phase 18).
- Understanding contamination canaries.
- RDS v0.2 feature vector interpretation.

### 20.6 `harness-setup-guide.md`

Covers:

- Writing `AGENTS.md` with HC1-HC6 constraints.
- Runtime overlays: `CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`.
- Permission profiles and the six modes.
- Running harness drift checks: `evidence-sca check-drift`.
- AI-readiness score: five axes, four stage thresholds.
- Session telemetry: what is recorded and where.
- Budget configuration.
- Memory opt-in: what is stored, what is not.

### 20.7 `incident-response-guide.md`

Covers:

- How to open an incident: `evidence-sca record-incident <run_id>`.
- P0/P1/P2 classification criteria.
- Using `evidence-sca diagnose <incident_id>` for trace replay.
- Incident fields: impact, timeline, root cause, containment, remediation, evidence links.
- Linking a detector follow-up.
- Closing an incident with reviewer sign-off.
- Promoting a lesson: `evidence-sca promote-lesson <source_run_id>`.
- Rollback path documentation requirements.

### 20.8 Documentation Rules

Rules:

- Each guide must include a "Limitations" section stating what the tool cannot do.
- Each guide must reference the `HarnessConditionSheet` and explain what it means.
- No guide may claim a workflow produces correct results without evidence; all quality claims reference the Phase 18 calibration reports.
- Documentation is part of the release artefact set; a release cannot proceed with broken links or missing required sections.

---

## 21. Test Plan

### 21.1 Hardening Tests

Required:

- Cache invalidation fires on `graph_update` completion.
- File watcher triggers `graph_update` on file change.
- Git hook installer installs and uninstalls cleanly.
- Graph chunker splits large graph fixture into correct chunks.
- Subscription recovery sends missed notifications on reconnect.
- Task TTL hard-cap enforced.
- Authorization context binding prevents cross-context task access.

### 21.2 Permission Profile Tests

Required:

- All six modes correctly allow/deny tool calls.
- Profile change recorded in governance ledger.
- Widened profile triggers `relaxed` drift finding.

### 21.3 Session Replay and Diagnosis Tests

Required:

- Replay reconstructs event sequence from fixture run record.
- Replay `--diff-run` shows correct delta.
- Diagnosis shows incident fields and linked events.
- Both commands produce identical output for same inputs (idempotent).

### 21.4 Privacy and Ledger Tests

Required:

- Secret scan at write time rejects secret-containing record.
- PII detection redacts email address in run event.
- Ledger export produces JSONL archive.
- Ledger delete executes with audit trail.

### 21.5 HTTP Transport Tests

Required:

- Server starts in HTTP mode.
- Resource read succeeds over HTTP.
- Tool call succeeds over HTTP.
- CORS wildcard origin rejected.
- Unauthenticated request rejected when auth required.

### 21.6 Packaging Tests

Required:

- `hatch build` produces wheel and sdist.
- Wheel installs cleanly in a fresh virtual environment.
- CLI `evidence-sca --version` works after install.
- MCP server starts after install.

---

## 22. Work Packages

### P19.1 Cache Invalidation Hardening

Build: `CacheInvalidationHardener`; subscription to `graph_update`; cache-key invalidation logic; verify diagnostic.

Acceptance: Cache invalidated for fixture file change.

### P19.2 File Watcher and Git Hooks

Build: `FileWatcherService` with `watchdog`; `GitHookInstaller`; asyncio integration.

Acceptance: File change triggers `graph_update`; hook installs and uninstalls.

### P19.3 Graph Chunker and Large-Graph Support

Build: `GraphChunker`; chunk-by-module logic; lazy chunk serving.

Acceptance: Large fixture graph chunked correctly; manifest returns chunk references.

### P19.4 Subscription Recovery and Task Hardening

Build: `SubscriptionRecoveryManager`; task TTL pruner; authorization context binding hardener.

Acceptance: Missed notifications recovered; expired tasks pruned; cross-context access blocked.

### P19.5 Permission Profile Hardening

Build: `PermissionProfileSet` model; six-mode enforcement; profile-change ledger event.

Acceptance: All six modes correct; profile change recorded.

### P19.6 Devcontainer and Sandbox Templates

Build: `.devcontainer/devcontainer.json`; CI sandbox workflow template.

Acceptance: Devcontainer starts MCP server; CI template runs T1 smoke.

### P19.7 Session Replay and Incident Diagnosis

Build: `SessionReplayTool` CLI; `IncidentDiagnosisTool` CLI; Rich-rendered output.

Acceptance: Replay reconstructs fixture run; diagnosis shows incident fields.

### P19.8 Ledger Retention, Export, and Delete

Build: `LedgerRetentionPolicy` model; `LedgerExporter`; `LedgerDeleteTool`; audit trail.

Acceptance: Export produces JSONL; delete records audit trail.

### P19.9 Trace Redaction Audit and Sampled Replay

Build: `TraceRedactionAuditor`; sampled replay background task; `trace_replay_failure` monitor event.

Acceptance: Secret-containing fixture run event flagged by auditor.

### P19.10 Manifest Regression Runner

Build: `ManifestRegressionRunner`; integration with release gate command.

Acceptance: Snapshot change detected; gate blocks on breaking finding.

### P19.11 Cumulative Risk Monitor and Harness Drift Checker

Build: `CumulativeRiskMonitor` with six patterns; `HarnessDriftChecker` CLI; waiver support.

Acceptance: `repeated_identical_tool_calls` detected for fixture; relaxed drift fails CLI.

### P19.12 Privacy Controls

Build: `RetentionPolicy` model; privacy control pipeline; right-to-delete path.

Acceptance: PII redacted before persistence; delete audit trail written.

### P19.13 Streamable HTTP Transport

Build: `HTTPTransportConfig` model; HTTP startup mode; TLS validation; rate limiting; auth token enforcement.

Acceptance: Server starts in HTTP mode; CORS wildcard rejected; unauthenticated request rejected.

### P19.14 Packaging and Release Automation

Build: `hatch` configuration; release automation script; supply-chain provenance recording.

Acceptance: Wheel installs cleanly; CLI works after install.

### P19.15 Documentation

Build: Seven guides with Limitations sections; documentation test for broken links.

Acceptance: All seven guides present; no broken links; Limitations sections present.

---

## 23. Suggested Implementation Order

Recommended order:

1. Permission profile hardening.
2. Cache invalidation hardening.
3. Graph chunker.
4. Subscription recovery.
5. Task TTL and authorization hardening.
6. File watcher and git hooks.
7. Session replay CLI.
8. Incident diagnosis CLI.
9. Cumulative risk monitor.
10. Harness drift checker.
11. Manifest regression runner.
12. Trace redaction audit.
13. Sampled replay checks.
14. Ledger retention, export, and delete.
15. Privacy controls.
16. Streamable HTTP transport.
17. Devcontainer and sandbox templates.
18. Packaging and release automation.
19. Documentation (seven guides).

Reasoning:

- Permission and cache hardening must come before HTTP transport (the new surface area makes safe defaults critical).
- Session replay and diagnosis enable meaningful documentation examples.
- Packaging comes late because it depends on all features being stable.
- Documentation is last because it requires all features to be complete enough to document accurately.

---

## 24. Exit Criteria Mapping

Source Phase 19 exit criterion:

- Tool can be installed as a Python package.

Concrete acceptance: `pip install evidence-sca` in a clean venv; `evidence-sca --version` succeeds; MCP server starts.

Source Phase 19 exit criterion:

- Local MCP server can index and serve a multi-repo workspace.

Concrete acceptance: Fixture with two registered repos: `evidence-sca graph-build` produces manifests for both; `code-intelligence://repos` lists both.

Source Phase 19 exit criterion:

- Documentation explains limitations, confidence behaviour, and release gates.

Concrete acceptance: `architecture.md` and `evaluation-guide.md` contain Limitations sections; evidence hierarchy documented; release gate thresholds documented.

Source Phase 19 exit criterion:

- Documentation explains the harness condition, permission profiles, telemetry, memory governance, and rollback path.

Concrete acceptance: `harness-setup-guide.md` covers all five topics; `incident-response-guide.md` documents rollback path requirements.

Source Phase 19 exit criterion:

- A production release can be diagnosed from run records, operational ledger entries, incidents, budget events, and policy decisions.

Concrete acceptance: `evidence-sca replay <run_id>` and `evidence-sca diagnose <incident_id>` both work from the operational store alone, without the original source repository.

Source Phase 19 exit criterion:

- Re-running the harness check is idempotent when no drift exists.

Concrete acceptance: Running `evidence-sca check-drift <repo>` twice on an unchanged repo produces identical output.

---

## 25. Definition Of Done

Phase 19 is done when:

- Cache invalidation fires on `graph_update` and invalidates affected cache keys.
- File watcher triggers `graph_update` on file change; git hooks install and uninstall cleanly.
- Large graph chunker splits graphs into `max_chunk_nodes`-bounded chunks.
- Subscription recovery sends missed notifications on reconnect.
- Task TTL hard-cap enforced; authorization context binding prevents cross-context task access.
- All six permission modes correctly allow/deny tool calls.
- Devcontainer template starts MCP server without modification.
- Session replay reconstructs event sequence; incident diagnosis shows all required fields.
- Ledger export and delete work with audit trails.
- Trace redaction audit detects unredacted secrets in fixture run.
- Manifest regression runner detects snapshot changes and blocks release gate.
- Cumulative risk monitor detects all six pattern types.
- Harness drift checker classifies artefacts correctly; `relaxed` drift fails CLI.
- Privacy controls redact PII before persistence; right-to-delete path documented.
- Streamable HTTP transport starts; CORS wildcard rejected; auth enforced.
- Wheel installs cleanly; `evidence-sca --version` works; MCP server starts after install.
- All seven documentation guides present with Limitations sections and no broken links.
- Supply-chain provenance recorded for the release.

---

## 26. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| HTTP transport introduces new attack surface | Unauthenticated access to MCP tools | TLS required for non-localhost; auth token enforced; CORS wildcard blocked; rate limiting active |
| File watcher misses events on high-traffic repos | Stale graph | Debounce window; full rebuild fallback when event queue overflows; diagnostic logged |
| Large graph chunking produces inconsistent slices | Query returns split results | Chunk boundaries follow module topology; overlap region defined; test with large fixture graph |
| Permission hardening breaks existing workflows | Regression in tool access | Six modes tested with fixture scenarios before release; mode changes require explicit config update |
| Documentation lags feature implementation | Users rely on outdated docs | Documentation included as a P19 gate; release blocked if sections missing |
| Packaging wheel includes test fixtures or secrets | Supply-chain contamination | `hatch build` targets exclude `tests/`, secrets baseline, and JSONL trace files; `detect-secrets` scan before publish |
| Cumulative risk monitor produces false positives | Workflow blocked unnecessarily | Thresholds configurable per policy; initial thresholds are conservative; false positives generate warnings, not hard blocks |
| `relaxed` drift check false positive | CI blocked without real policy weakening | Drift check documents what counts as `relaxed`; exceptions require waiver with reason and expiry |

---

## 27. Phase 19 Completion Report Template

When Phase 19 implementation is complete, report:

```text
Phase 19 completion report

Implemented:
- Cache invalidation hardening:
- File watcher (watchdog):
- Git hook installer:
- Graph chunker:
- Subscription recovery:
- Task TTL and auth hardening:
- Permission profile hardening (6 modes):
- Devcontainer template:
- CI sandbox template:
- Session replay CLI:
- Incident diagnosis CLI:
- Ledger retention/export/delete:
- Trace redaction audit:
- Sampled replay checks:
- Manifest regression runner:
- Cumulative risk monitor (6 patterns):
- Harness drift checker:
- Privacy controls:
- Streamable HTTP transport:
- Packaging (wheel + sdist):
- Release automation script:
- Documentation (7 guides):

Exit criteria:
- Tool installs as Python package:
- Multi-repo workspace indexed and served:
- Documentation covers limitations, confidence, release gates:
- Documentation covers harness condition, permission, telemetry, memory, rollback:
- Production release diagnosable from run records alone:
- Harness check idempotent when no drift:

Known limitations:
-
```

---

## 28. Minimal First Slice Within Phase 19

If Phase 19 needs to be split further, implement this first:

1. Permission profile hardening.
2. Cache invalidation hardening.
3. Graph chunker.
4. Session replay CLI (basic event list).
5. `installation.md` and `quickstart.md` guides.
6. Packaging (`hatch build` produces installable wheel).
7. Supply-chain provenance recording.
8. `evidence-sca --version` CLI command.

This minimal slice makes the package installable, makes the graph usable with large repos, and establishes the session replay baseline that the remaining operational tools build on.
