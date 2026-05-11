# LLM-SCA Tooling Phase 4 Implementation Plan: MCP Server Core

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 4 - MCP Server Core  
> Primary objective: expose the repository index through stable MCP resources, tools, prompt stubs, long-running task support, permission metadata, task telemetry, resource subscriptions, and update notifications.

---

## 1. Phase Summary

Phase 4 is the first server-facing phase of `evidence-sca`. Phase 1 defined typed contracts, Phase 2 persisted data, and Phase 3 produced the first repository graph. Phase 4 exposes that indexed evidence through an MCP server named `code-intelligence`.

This phase should make the index usable by MCP clients without introducing full high-level workflows yet. The server should list resources, route resource reads, call query/build tools, run `graph_build` as a task-capable operation, emit resource update notifications, expose permission descriptors, record basic trace events, and provide public prompt stubs that assemble instructions and suggested resources/tools without executing complete workflows.

The central rule for this phase is:

```text
MCP results must be schema-first and evidence-preserving.
No tool or prompt should return unstructured claims when a typed graph, run, task,
permission, snapshot, or diagnostic payload exists.
```

Phase 4 should implement:

- MCP server runtime.
- Resource routing for the core index resources.
- Query and build tool routing.
- Long-running task wrapper and persistence.
- Task polling, result retrieval, cancellation, TTL, progress, and restart recovery.
- Resource subscriptions and update/list-changed notifications.
- Capability detection for MCP Sampling.
- Tool permission descriptors.
- Tool-description and prompt regression tests.
- Public prompt stubs for later workflows.

### Architecture Coverage

Phase 4 covers:

- MCP resources.
- MCP tools.
- MCP prompt templates.
- Async task model.
- Resource update notifications.

Backing resources for this phase:

- `code-intelligence://repos`
- `code-intelligence://schema/graph.schema.json`
- `code-intelligence://schema/run-record.schema.json`
- `code-intelligence://graph/{repo}`
- `code-intelligence://graph/slice/{repo}/{files}`
- `code-intelligence://summary/{repo}/{symbol_path}`
- `code-intelligence://blame/{repo}/{file_path}`
- `code-intelligence://build-evidence/{repo}`

Tools in this phase:

- `register_repo`
- `graph_build`
- `graph_update`
- `plugin_reload`
- `get_graph_slice`
- `find_callers`
- `find_callees`
- `git_blame_chain`

Prompt stubs in this phase:

- `implementation-check`
- `bug-resolve`
- `patch-review`
- `operational-review`
- `readiness-audit`

### Inherited Paper Anchors

Use these anchors in Phase 4 issues, ADRs, protocol notes, and regression reports:

- `rig`
- `logiclens`
- `predicatefix`
- `swe-bench-live`
- `swd-bench`
- `swe-polybench`

Adjacent anchors useful for task, trace, and harness notes:

- `agenttrace`
- `aer`
- `opendev`
- `runtime-governance`
- `workstream`
- `tdad`

## Technology Stack

Libraries and tools active in Phase 4. All versions are minimum constraints; exact pins are in `uv.lock`. Run every command via `uv run`.

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| FastMCP | `fastmcp` | >=2.0 | MCP server framework; resource, tool, and prompt registration via decorators; stdio transport in this phase |
| FastAPI | `fastapi` | >=0.115 | Async HTTP server framework; included in the dependency set from Phase 0; Streamable HTTP transport activated in Phase 19 |
| uvicorn | `uvicorn[standard]` | >=0.30 | ASGI server for FastAPI; listed as a production dependency from Phase 4 onward; not required for stdio-only deployments but included for dependency stability |
| orjson | `orjson` | >=3.10 | MCP resource payload serialisation; SARIF and run-record JSONL I/O |
| Pydantic v2 | `pydantic` | >=2.0 | All MCP resource/tool/task/permission models; `model_config = ConfigDict(extra="forbid")` on stable contract objects; `model.model_json_schema()` for JSON Schema export |
| SQLModel | `sqlmodel` | >=0.0.21 | Task persistence layer; graph store reads for resource routing |
| aiosqlite | `aiosqlite` | >=0.20 | Async SQLite driver for dev/CI |
| NetworkX | `networkx` | >=3.3 | In-memory subgraph loads for `find_callers` / `find_callees` tool responses |

**Transport plan.**

| Phase | Transport | Rationale |
|---|---|---|
| Phase 4 | stdio | Default for local IDE and Claude Code integration |
| Phase 19 | stdio + Streamable HTTP | Multi-client and remote deployment |

FastMCP server entry point pattern:

```python
from fastmcp import FastMCP

mcp = FastMCP("code-intelligence")

@mcp.resource("code-intelligence://repos")
async def list_repos() -> list[dict]: ...

@mcp.tool()
async def graph_build(repo_path: str) -> dict: ...
```

**All MCP resource handlers and tool handlers are `async def`.** No synchronous handlers in the MCP layer.

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 4 depends on:

- Phase 1 schemas:
  - graph schema
  - run-record schema
  - harness condition schema
  - permission and policy models
  - artefact references
  - graph diagnostics
- Phase 2 stores:
  - repository registry
  - snapshot ledger
  - graph store
  - operational store
  - artefact registry
  - harness metadata store
- Phase 3 indexing:
  - graph build service
  - graph update service
  - graph slice generator
  - graph manifests
  - blame-chain records
  - build/test evidence records
  - summary cache records
  - indexing operational events

### Phase Outputs

Phase 4 should produce:

- MCP server module.
- Resource registry and URI router.
- Tool registry and tool-call router.
- Prompt registry.
- Task manager.
- Task persistence layer.
- Notification and subscription manager.
- Permission descriptor model for MCP tools.
- Capability negotiation record, including Sampling availability.
- Tool telemetry hooks.
- MCP protocol tests.
- Tool-description regression tests.
- Prompt regression tests.
- Minimal CLI or dev command to run the MCP server.

### Non-Goals

Do not implement these in Phase 4:

- Full Phase 4A operational harness runtime tools.
- Fault localisation.
- Repo-QA.
- SARIF/static-analysis execution.
- Cross-language plugin indexing beyond a `plugin_reload` stub or no-op capability.
- Patch review execution.
- Bug resolution workflow.
- Implementation-check workflow.
- Evaluation suite execution.
- Memory retrieval.
- Dynamic tracing.
- Production authentication system.

Phase 4 may define task/result shapes and permission metadata for future tools, but should not fake completed workflow behavior.

---

## 3. Recommended File Layout

Assuming package name `evidence_sca`:

```text
src/evidence_sca/
  mcp_server/
    __init__.py
    server.py
    app.py
    config.py
    context.py
    capabilities.py
    errors.py
    resources.py
    resource_registry.py
    resource_uris.py
    tools.py
    tool_registry.py
    tool_permissions.py
    prompts.py
    prompt_registry.py
    tasks.py
    task_store.py
    task_runner.py
    task_ids.py
    notifications.py
    subscriptions.py
    telemetry.py
    serialization.py
    sampling.py
    dev_server.py

  mcp_server/resources/
    __init__.py
    repos.py
    schemas.py
    graph.py
    summaries.py
    blame.py
    build_evidence.py

  mcp_server/tools/
    __init__.py
    registry.py
    graph.py
    blame.py
    plugins.py

  mcp_server/prompts/
    implementation_check.md
    bug_resolve.md
    patch_review.md
    operational_review.md
    readiness_audit.md

tests/
  mcp_server/
    fixtures/
      resource_payloads/
      tool_descriptions/
      prompt_cases/
    test_server_startup.py
    test_resource_registry.py
    test_resource_routing.py
    test_schema_resources.py
    test_graph_resources.py
    test_tool_registry.py
    test_graph_tools.py
    test_task_manager.py
    test_task_restart_recovery.py
    test_notifications.py
    test_subscriptions.py
    test_prompt_registry.py
    test_tool_permission_descriptors.py
    test_tool_description_regressions.py
    test_prompt_regressions.py
```

If the repository still uses the earlier package name, keep these boundaries and migrate names later.

---

## 4. Server Runtime

### 4.1 Runtime Responsibilities

The MCP server runtime should:

- Start and stop cleanly.
- Load server configuration.
- Open the Phase 2 workspace store.
- Register resources, tools, prompts, and task handlers.
- Advertise server capabilities.
- Validate requests.
- Serialize responses through Phase 1 schemas.
- Emit structured errors.
- Record basic telemetry for tool calls and tasks.
- Shut down active tasks according to policy.

### 4.2 Server Name

Use:

```text
code-intelligence
```

This preserves the architecture surface even though the repository is named `evidence-sca`.

### 4.3 Configuration

Recommended config fields:

```text
McpServerConfig
  workspace_path
  server_name
  server_version
  transport
  single_user
  enable_tasks
  enable_task_list
  enable_task_cancel
  task_ttl_seconds_default
  task_ttl_seconds_max
  task_poll_interval_seconds
  resource_subscription_enabled
  sampling_enabled
  max_resource_bytes
  max_graph_slice_nodes
  max_graph_slice_edges
  redaction_policy
  telemetry_enabled
```

Defaults:

- Tasks enabled.
- `tasks/list` disabled for unauthenticated local multi-user mode.
- Resource subscriptions enabled.
- Sampling detection enabled, but no workflow should require Sampling in Phase 4.
- Resource size limits enforced.

### 4.4 Development Entrypoint

Recommended command:

```text
evidence-sca mcp serve --workspace .evidence-sca
```

If CLI is not ready:

```text
python -m evidence_sca.mcp_server.dev_server --workspace .evidence-sca
```

### 4.5 Startup Checks

On startup:

- Verify workspace store is present and compatible.
- Verify schema files can be loaded.
- Verify resource registry has no duplicate URI templates.
- Verify tool registry has no duplicate names.
- Verify prompt registry has required prompt stubs.
- Verify task store can be opened.
- Record capability descriptor.

### 4.6 Runtime Tests

Required tests:

- Server starts with empty workspace.
- Server starts with indexed fixture workspace.
- Duplicate resource registration fails.
- Duplicate tool registration fails.
- Missing schema file fails startup.
- Incompatible workspace fails startup clearly.
- Server reports capability descriptor.

---

## 5. Resource Routing

### 5.1 Resource Registry

The resource registry maps URI patterns to handlers.

Recommended handler interface:

```text
ResourceHandler
  uri_pattern
  listable
  subscribable
  read(context, uri, params) -> ResourceResult
  list(context) -> list[ResourceDescriptor]
```

Recommended `ResourceResult`:

```text
ResourceResult
  uri
  media_type
  schema_version
  payload
  artifact_refs
  snapshot_refs
  diagnostics
  redaction_status
  etag
  updated_ts
```

Rules:

- Resource results should be schema-first.
- Large resource payloads should return manifests or artefact references.
- Resource reads must include freshness/snapshot metadata where relevant.
- Missing resources should return typed not-found errors.
- Stale resources should not be hidden.

### 5.2 Resource URI Parsing

Implement strict URI parsing for:

- Scheme.
- Authority.
- Path segments.
- Encoded repo IDs.
- File path parameters.
- Symbol path parameters.

Rules:

- Reject path traversal.
- Decode URI-escaped file paths safely.
- File paths must remain repo-relative.
- URI parsing should not query the store until syntactic validation passes.

### 5.3 Resource Descriptors

Each resource descriptor should include:

- URI or URI template.
- Name.
- Description.
- MIME/media type.
- Schema family/version.
- Whether it is subscribable.
- Expected size class.
- Freshness semantics.

### 5.4 Resource Error Types

Recommended errors:

- `ResourceNotFound`
- `ResourceInvalidUri`
- `ResourceTooLarge`
- `ResourceStale`
- `ResourceUnavailable`
- `ResourcePermissionDenied`
- `ResourceSchemaError`

---

## 6. Core Index Resources

### 6.1 `code-intelligence://repos`

Purpose:

- List registered repositories and current index status.

Backing store:

- Phase 2 repository registry.
- Latest snapshot ledger.
- Optional indexing result summary from Phase 3.

Payload should include:

- Repo ID.
- Name.
- Redacted root reference.
- VCS type.
- Current branch.
- Latest snapshot ID.
- Git SHA or dirty worktree snapshot ID.
- Dirty flag.
- Index status.
- Last indexed timestamp.
- Diagnostics summary.
- Capabilities.

Rules:

- Do not expose absolute paths unless policy allows.
- Include stale/partial/failed status.
- Resource list changes when repos are registered/unregistered.

Tests:

- Empty repo list.
- One registered repo.
- Dirty indexed repo.
- Stale repo status.
- Redacted root path.

### 6.2 `code-intelligence://schema/graph.schema.json`

Purpose:

- Serve the checked-in graph schema.

Backing store:

- Phase 1 schema export.

Payload:

- JSON Schema for graph model.

Rules:

- Schema resource is read-only.
- Schema version in payload must match server schema version.
- Result should be cacheable with an ETag/hash.

Tests:

- Schema resource returns valid JSON.
- Missing schema fails startup or resource read clearly.
- Schema hash is stable.

### 6.3 `code-intelligence://schema/run-record.schema.json`

Purpose:

- Serve the checked-in run-record schema.

Backing store:

- Phase 1 schema export.

Payload:

- JSON Schema for run records and run events.

Rules:

- Read-only.
- Versioned.
- Stable hash.

Tests:

- Schema resource returns valid JSON.
- Schema version matches model constants.

### 6.4 `code-intelligence://graph/{repo}`

Purpose:

- Return graph manifest plus chunk references for a repo.

Backing store:

- Phase 2 graph manifest table.
- Phase 2 artefact registry.
- Phase 3 manifest generation.

Payload should include:

- Graph ID.
- Repo ID.
- Snapshot ID.
- Git SHA or worktree snapshot ID.
- Node count.
- Edge count.
- Node type counts.
- Edge type counts.
- Chunk artefact refs.
- Diagnostics summary.
- Generated timestamp.
- Indexing run ID.
- Schema version.

Rules:

- Never return a full graph dump by default.
- If no graph exists, return not indexed or not found with actionable diagnostics.
- Include stale/dirty/partial snapshot status.
- Graph chunks are artefacts with hashes.

Tests:

- Graph manifest returned for indexed fixture.
- Large graph does not inline all nodes.
- Missing graph returns typed not-found.
- Dirty graph includes worktree snapshot ID.

### 6.5 `code-intelligence://graph/slice/{repo}/{files}`

Purpose:

- Return bounded graph slices around one or more files.

Backing store:

- Phase 2 graph queries.
- Phase 3 graph slice generator.

Payload should include:

- Repo ID.
- Requested files.
- Requested snapshot if present.
- Actual snapshot IDs.
- Snapshot consistency.
- Nodes.
- Edges.
- Diagnostics.
- Truncation metadata.
- Provenance summary.

Rules:

- Include files, symbols, imports, tests, and provenance when available.
- Mixed snapshots must be explicit.
- Truncated slices must be explicit.
- File paths must be repo-relative and URI-decoded safely.

Tests:

- File slice returns expected fixture nodes and edges.
- Multi-file slice works.
- Invalid file path rejected.
- Mixed-snapshot slice reports mixed status.
- Truncation is explicit.

### 6.6 `code-intelligence://summary/{repo}/{symbol_path}`

Purpose:

- Return cached symbol summary for a symbol.

Backing store:

- Phase 3 summary cache.

Payload should include:

- Summary ID.
- Repo ID.
- Symbol node ID.
- Symbol path.
- File path.
- Span.
- Snapshot ID.
- Summary text.
- Confidence.
- Derivation.
- Generator ID.
- Current/invalidated status.
- Provenance.

Rules:

- Return cache miss explicitly.
- Invalidated summaries should not be served as current unless requested by debug mode.
- Summary evidence is low-confidence or hybrid, never parser fact.
- Include snapshot identity.

Tests:

- Current summary returned.
- Cache miss returned clearly.
- Invalidated summary not returned as current.
- Dirty snapshot summary key works.

### 6.7 `code-intelligence://blame/{repo}/{file_path}`

Purpose:

- Return git blame-chain evidence for a file.

Backing store:

- Phase 3 blame-chain records or artefacts.

Payload should include:

- Blame ID.
- Repo ID.
- File path.
- Snapshot ID.
- Git SHA or worktree snapshot ID.
- Line entries or artefact ref.
- Commit chain.
- Diagnostics.
- Provenance.

Rules:

- Blame missing for untracked files should be diagnostic, not silent failure.
- Large blame payloads may be artefact references.
- File path must be repo-relative.

Tests:

- Blame returned for committed fixture file.
- Untracked/dirty file diagnostic.
- Missing file returns typed error.

### 6.8 `code-intelligence://build-evidence/{repo}`

Purpose:

- Return detected build/test/CI evidence.

Backing store:

- Phase 3 build/test evidence graph nodes and artefacts.

Payload should include:

- Package manager files.
- Test directories.
- Test framework hints.
- CI jobs.
- Build targets.
- Evidence graph node IDs.
- Snapshot ID.
- Diagnostics.
- Provenance.

Rules:

- Detection does not imply tests were executed.
- Unsupported config parse should be diagnostic.
- Include snapshot identity.

Tests:

- Pytest evidence returned for fixture.
- CI workflow evidence returned.
- No tests detected returns empty evidence with status, not error.

---

## 7. Tool Registry

### 7.1 Tool Descriptor

Each tool should expose:

- Name.
- Description.
- Input schema.
- Output schema.
- Whether it is read-only.
- Whether it is long-running.
- Task support level.
- Required permission mode.
- Path scope.
- Network requirement.
- Side-effect class.
- Approval requirement.
- Emits resource notifications.
- Emits run/task telemetry.

### 7.2 Tool Handler Interface

Recommended interface:

```text
ToolHandler
  name
  descriptor()
  validate_args(args) -> TypedArgs
  call(context, args) -> ToolResult | TaskCreateResult
```

Recommended `ToolResult`:

```text
ToolResult
  tool_name
  status
  payload
  schema_version
  artifact_refs
  diagnostics
  run_event_ids
  notifications
```

### 7.3 Tool Error Types

Recommended errors:

- `ToolNotFound`
- `ToolInvalidArguments`
- `ToolPermissionDenied`
- `ToolApprovalRequired`
- `ToolExecutionFailed`
- `ToolTaskRequired`
- `ToolUnavailable`
- `ToolSchemaError`

### 7.4 Tool Permission Descriptors

Permission descriptor fields:

- `required_mode`
- `path_scope`
- `network_requirement`
- `side_effect_class`
- `approval_requirement`
- `allowed_stages`
- `writes_to_store`
- `writes_to_repo`
- `runs_subprocesses`

Rules:

- Descriptors are declarative and testable.
- Phase 4 records descriptors; Phase 4A implements full deterministic policy evaluation.
- Tools should still refuse clearly unsafe or out-of-scope arguments in Phase 4.

---

## 8. Phase 4 Tools

### 8.1 `register_repo`

Purpose:

- Register a repository in the workspace.

Input:

```text
repo_path
name?
policy_scope?
```

Output:

- Repository record.
- Current index status.
- Resource list-changed notification marker.

Behavior:

- Calls Phase 2 repository registry.
- Does not index files unless explicitly configured later.
- Emits `notifications/resources/list_changed` because `code-intelligence://repos` changes.

Permissions:

- Required mode: read/search.
- Path scope: target repo root.
- Network: none.
- Side effect: writes local workspace store.
- Approval: not required by default.

Tests:

- Registers repo.
- Duplicate registration idempotent.
- Invalid path rejected.
- List-changed notification emitted.

### 8.2 `graph_build`

Purpose:

- Start full index build for one or more repos.

Input:

```text
repo_paths | repo_ids
config?
task?
```

Output:

- Immediate result for very small/synchronous mode, or task create result.
- Final task result is Phase 3 `IndexingResult`.

Behavior:

- Task-capable and usually long-running.
- Calls Phase 3 indexing service.
- Emits task status/progress events.
- Emits resource update notifications for repos, graph, graph slices, summary, blame, and build evidence when complete.
- Links task events to run records where a run exists.

Permissions:

- Required mode: execute for indexing backend subprocesses, or read/search when using pure Python backend only.
- Path scope: registered repo roots.
- Network: none.
- Side effect: writes local workspace store and artefacts.
- Approval: not required by default.

Tests:

- Starts as task.
- Produces high-entropy task ID.
- Polling returns progress.
- Completed result includes indexing result.
- Resource update notifications emitted.
- Task result survives restart within TTL.

### 8.3 `graph_update`

Purpose:

- Incrementally update index for one or more repos or snapshots.

Input:

```text
repo_paths? | repo_ids?
snapshot?
config?
task?
```

Output:

- Task create result or update result.

Behavior:

- Task-capable.
- Calls Phase 3 update service.
- Detects changed files through Phase 3.
- Emits resource updates on completion.
- Emits stale/dirty snapshot progress where relevant.

Permissions:

- Required mode: execute or read/search depending on backend config.
- Path scope: registered repo roots.
- Network: none.
- Side effect: writes local workspace store and artefacts.

Tests:

- Starts update task.
- Handles no changes.
- Emits graph and summary update notifications for changed files.
- Cancellation can stop queued/running update according to policy.

### 8.4 `plugin_reload`

Purpose:

- Placeholder hook for reloading interface plugins.

Input:

```text
plugin_id?
```

Output:

- In Phase 4, either no-op capability result or `not_implemented_until_phase_7`.

Behavior:

- Should not pretend plugins were indexed.
- Emits list-changed notification only when plugin registry actually changes.
- Keeps tool surface stable for later Phase 7.

Permissions:

- Required mode: read/search for no-op.
- Path scope: workspace/plugin config.
- Network: none.
- Side effect: none in Phase 4, later writes index/plugin records.

Tests:

- Returns explicit not-implemented/capability result.
- Does not emit false graph updates.

### 8.5 `get_graph_slice`

Purpose:

- Return a bounded typed graph slice.

Input:

```text
repo
files?
symbols?
edge_types?
node_types?
depth?
limit?
snapshot?
```

Output:

- Graph slice payload.

Behavior:

- Calls Phase 3 graph slice generator or Phase 2 graph queries.
- Read-only.
- Includes snapshot consistency, provenance, confidence, diagnostics, and truncation.

Permissions:

- Required mode: read/search.
- Path scope: registered repos.
- Network: none.
- Side effect: none except optional telemetry.

Tests:

- Returns fixture slice.
- Rejects unregistered repo.
- Rejects unsafe file path.
- Preserves mixed snapshot status.

### 8.6 `find_callers`

Purpose:

- Return graph callers for a symbol.

Input:

```text
repo?
symbol
depth?
include_cross_repo?
snapshot?
```

Output:

- Caller graph slice or structured caller list.

Behavior:

- Uses `calls` edges in graph store.
- Phase 4 does not require cross-language plugin traversal yet.
- If cross-language traversal is requested but unavailable, return explicit capability diagnostic.

Permissions:

- Required mode: read/search.
- Network: none.
- Side effect: none.

Tests:

- Finds same-repo callers in fixture graph.
- Unknown symbol returns empty result with diagnostic.
- Cross-language unavailable is explicit.

### 8.7 `find_callees`

Purpose:

- Return graph callees for a symbol.

Input:

```text
repo?
symbol
depth?
include_cross_repo?
snapshot?
```

Output:

- Callee graph slice or structured callee list.

Behavior:

- Uses `calls` edges in graph store.
- Same fallback behavior as `find_callers`.

Tests:

- Finds same-repo callees.
- Handles unresolved dynamic call candidates as low-confidence or diagnostic.

### 8.8 `git_blame_chain`

Purpose:

- Return blame-chain evidence for a file or file location.

Input:

```text
repo
file
line?
snapshot?
```

Output:

- Blame-chain payload or artefact reference.

Behavior:

- Reads Phase 3 blame records.
- Does not run git blame live unless Phase 3 service exposes a safe refresh option.
- Includes dirty/untracked diagnostics.

Permissions:

- Required mode: read/search.
- Path scope: registered repo.
- Network: none.
- Side effect: none.

Tests:

- Returns blame for fixture file.
- Line-specific query filters line entry.
- Missing blame record returns cache-miss diagnostic.

---

## 9. Task Model

### 9.1 Purpose

Long-running MCP operations should follow a call-now/fetch-later model. Phase 4 must support `graph_build` as a task and define reusable task infrastructure for later phases.

### 9.2 Task-Capable Tools

Phase 4 task-capable tools:

- `graph_build`
- `graph_update`

Later task-capable tools:

- `run_static_analysis`
- `run_sast_repair`
- `classify_patch_risk`
- `capture_trace`
- `run_issue_resolution`
- `run_implementation_check`
- `run_patch_review`
- `run_operational_review`
- `run_readiness_audit`
- `run_eval_suite`

### 9.3 Task Descriptor

Tool descriptors for long-running tools should include:

```text
execution.taskSupport: optional | required
```

Also expose:

- Default TTL.
- Maximum TTL.
- Suggested poll interval.
- Cancellation support.
- Result availability after completion.

### 9.4 Task Record

Recommended fields:

```text
TaskRecord
  task_id
  tool_name
  status
  created_ts
  started_ts
  updated_ts
  completed_ts
  expires_ts
  ttl_seconds
  poll_interval_seconds
  progress
  authorization_context_hash
  input_hash
  input_artifact_ref
  result_artifact_ref
  error
  run_id
  event_ids
  cancellation_requested
  metadata
```

Task status values:

- `created`
- `queued`
- `running`
- `cancelling`
- `cancelled`
- `failed`
- `completed`
- `expired`

### 9.5 Task IDs

Rules:

- Task IDs must be high entropy.
- Task IDs are sensitive capabilities.
- Do not use predictable counters.
- Do not include repo path or user data.
- Bind task state/results to authorization context where supported.
- In local unauthenticated multi-user mode, disable broad task listing unless explicitly single-user.

Recommended ID format:

```text
task:<urlsafe-random-token>
```

### 9.6 Task API Behavior

Required operations:

- Start task from task-capable tool call.
- Poll task status.
- Fetch task result.
- Cancel task when supported.
- Recover task state after server restart.
- Expire old tasks after TTL.

Optional operation:

- List tasks, only when allowed by server policy.

### 9.7 Task Persistence

Phase 4 can persist tasks using:

- A new task table in Phase 2 storage, or
- Operational records plus artefacts, if table changes are deferred.

Recommended table if adding migration:

```sql
CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  tool_name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  started_ts TEXT,
  updated_ts TEXT NOT NULL,
  completed_ts TEXT,
  expires_ts TEXT NOT NULL,
  ttl_seconds INTEGER NOT NULL,
  poll_interval_seconds INTEGER NOT NULL,
  progress_json TEXT NOT NULL,
  authorization_context_hash TEXT,
  input_hash TEXT NOT NULL,
  input_artifact_id TEXT,
  result_artifact_id TEXT,
  error_json TEXT,
  run_id TEXT,
  cancellation_requested INTEGER NOT NULL,
  metadata_json TEXT NOT NULL
);
```

### 9.8 Task Progress Events

Progress payload should include:

- Stage.
- Message.
- Percent if known.
- Counts if known.
- Current backend/tool if applicable.
- Diagnostics count.
- Artefact refs.
- Timestamp.

Examples:

- `scanner complete`
- `python_ast backend complete`
- `graph manifest generated`
- `summary cache invalidated`
- `dirty snapshot detected`
- `task cancellation requested`

### 9.9 Restart Recovery

Rules:

- Completed tasks remain fetchable until TTL.
- Failed tasks remain fetchable until TTL.
- Running tasks found on restart become `failed`, `cancelled`, or `unknown` according to recovery policy unless a resumable worker exists.
- Recovery events should be recorded.
- Result artefacts must be hash-verified before returning.

### 9.10 Cancellation

Rules:

- Cancellation is best-effort.
- Queued tasks can be cancelled before start.
- Running indexing tasks should check cancellation between pipeline stages.
- Cancellation must preserve partial diagnostics and run events.
- Cancelled tasks should not emit successful graph update notifications.

### 9.11 Task Tests

Required tests:

- Create task for `graph_build`.
- Task ID is high entropy and non-predictable.
- Poll queued/running/completed states.
- Fetch completed result.
- Fetch failed result with error.
- TTL expiration hides or expires result according to policy.
- Restart recovery marks in-flight task according to policy.
- Cancellation works for queued task.
- Cancellation is recorded for running task.
- Unauthorized task access denied when auth context exists.
- `tasks/list` disabled in unauthenticated multi-user mode.

---

## 10. Notifications And Subscriptions

### 10.1 Subscription Manager

Responsibilities:

- Track subscribed resource URIs.
- Validate subscribable resources.
- Emit update notifications.
- Emit list-changed notifications.
- Drop subscriptions on disconnect.
- Avoid leaking repo/resource data across authorization contexts.

### 10.2 Resource Update Notifications

Emit `notifications/resources/updated` after changes to:

- Graph manifests.
- Graph slices affected by changed files.
- Symbol summaries.
- Blame records.
- Build evidence.
- SARIF resources in later phases.
- Interface resources in later phases.
- Eval resources in later phases.
- Memory resources in later phases.
- Run resources in later phases.
- Readiness resources in later phases.
- Governance resources in later phases.
- Incident resources in later phases.

Phase 4 must at least emit updates for:

- `code-intelligence://repos`
- `code-intelligence://graph/{repo}`
- `code-intelligence://summary/{repo}/{symbol_path}` when invalidated/updated.
- `code-intelligence://blame/{repo}/{file_path}` when updated.
- `code-intelligence://build-evidence/{repo}`.

### 10.3 List-Changed Notifications

Emit `notifications/resources/list_changed` when:

- A repo is registered.
- A repo is unregistered.
- An interface plugin is registered, removed, or reloaded in later phases.

Phase 4 should emit list-changed for repo registration.

### 10.4 Notification Reliability

Rules:

- Notifications are advisory.
- Persisted store state is authoritative.
- Clients must be able to recover state by re-reading resources.
- Missed task progress notifications must be recoverable from task status or run events.

### 10.5 Subscription Tests

Required tests:

- Subscribe to repo resource.
- Subscribe to graph resource.
- Invalid subscription rejected.
- Repo registration emits list-changed.
- Graph build completion emits graph update.
- Graph update completion emits summary/blame/build-evidence updates.
- Notification loss does not affect persisted resource state.

---

## 11. Sampling Capability Detection

### 11.1 Purpose

MCP Sampling lets the server ask the client to invoke LLM subagents. Phase 4 should detect support and record capability, but not depend on Sampling for any core index operation.

### 11.2 Detection Record

Record in server capability/Harness Condition Sheet:

- Sampling supported.
- Sampling unsupported.
- Sampling unknown.
- Client capability details if available.

### 11.3 Fallback Behavior

Rules:

- If Sampling is unsupported, prompt stubs and future workflows must expose a fallback path.
- Phase 4 should not fail graph tools because Sampling is unavailable.
- Sampling support should be visible in task/run metadata.

### 11.4 Tests

Required tests:

- Sampling supported capability recorded.
- Sampling unsupported capability recorded.
- Prompt stub includes fallback note or metadata.
- Graph tools unaffected by Sampling availability.

---

## 12. Prompt Registry

### 12.1 Prompt Behavior

Prompt retrieval returns:

- Structured instructions.
- Arguments schema.
- Resource references.
- Suggested tool calls.
- Constraints and expected outputs.

Prompt retrieval does not:

- Execute long-running workflows.
- Mutate repositories.
- Claim final verdicts.
- Hide missing tools or unsupported capabilities.

### 12.2 Public Prompt Stubs

Required prompts:

- `implementation-check`
- `bug-resolve`
- `patch-review`
- `operational-review`
- `readiness-audit`

### 12.3 `implementation-check`

Arguments:

- `spec`
- `repos?`
- `policy?`

Assembles:

- Resource plan for graph/schema/build evidence.
- Suggested future launcher `run_implementation_check`.
- Current Phase 4 limitation that full workflow is not yet implemented.
- Evidence discipline: preserve `unknown` when ungrounded.

### 12.4 `bug-resolve`

Arguments:

- `issue_text`
- `repos?`
- `budget?`

Assembles:

- Suggested resources: repos, graph slices, summaries, blame, build evidence.
- Suggested future launcher `run_issue_resolution`.
- Current Phase 4 limitation that repair workflow is not yet implemented.

### 12.5 `patch-review`

Arguments:

- `diff`
- `context?`
- `repos?`
- `policy?`

Assembles:

- Suggested resources: graph slices around changed files, build evidence, future SARIF.
- Suggested future launcher `run_patch_review`.
- Sampling capability metadata and fallback note.

### 12.6 `operational-review`

Arguments:

- `run_id`
- `policy?`

Assembles:

- Suggested resources: run record and harness condition in Phase 4A.
- Current Phase 4 limitation if operational review launcher is unavailable.

### 12.7 `readiness-audit`

Arguments:

- `repo`
- `policy?`

Assembles:

- Suggested resources: repos, build evidence, future governance/readiness resources.
- Suggested future launcher `run_readiness_audit`.

### 12.8 Prompt Tests

Required tests:

- All required prompt names are registered.
- Prompt argument schema validates.
- Prompt retrieval returns structured instructions.
- Prompt retrieval does not execute tools.
- Prompt mentions unavailable workflow launcher as future/not implemented, not as successful.
- Prompt output is stable under snapshot tests.

---

## 13. Telemetry And Run Event Links

### 13.1 Phase 4 Scope

Phase 4 should emit basic trace events for MCP tool calls and task progress. Full policy evaluation, anomaly detection, readiness scoring, and operational review belong in Phase 4A.

### 13.2 Tool Telemetry

For each tool call, record:

- Tool name.
- Argument hash.
- Repo/path scope.
- Start timestamp.
- End timestamp.
- Status.
- Error category.
- Artefact refs.
- Token/cost fields if available, usually null in Phase 4.
- Redaction status.

### 13.3 Task Telemetry

For task-capable tools, record:

- Task created.
- Task started.
- Progress events.
- Cancellation requested.
- Task completed/failed/cancelled/expired.
- Result artefact reference.

### 13.4 Run Record Linking

Rules:

- If a tool call occurs inside an existing run context, append run events to that run.
- If no workflow run exists, task records still persist task telemetry.
- `graph_build` and `graph_update` should link to Phase 3 indexing run records where available.
- Missing run context is not fatal for standalone graph tools.

### 13.5 Tests

Required tests:

- Tool call emits telemetry event.
- Task progress emits telemetry.
- Graph build task links to indexing run ID when available.
- Redaction status is present.

---

## 14. Permission Metadata And Refusal Rules

### 14.1 Descriptor-First Policy

Phase 4 exposes permission metadata. It should also implement basic refusals for clearly unsafe requests, while leaving full policy engine behavior to Phase 4A.

### 14.2 Required Tool Metadata

Every tool descriptor must specify:

- Required mode.
- Path scope.
- Network requirement.
- Side-effect class.
- Approval requirement.

### 14.3 Basic Refusals

Refuse:

- Unregistered repo paths for graph queries unless `register_repo` is being called.
- Path traversal in resource URIs or tool args.
- Network-required behavior, because Phase 4 tools should not need network.
- Attempts to use `plugin_reload` as if Phase 7 plugins are available.
- Requests for full graph dumps that exceed resource limit.
- Task access with mismatched authorization context.

### 14.4 Regression Cases

Tool-description regression tests should cover:

- Tool order.
- Required permission metadata.
- Refusal on unsafe path.
- Refusal on unavailable feature.
- No broad network permission.
- No direct workflow execution through prompt retrieval.

---

## 15. Serialization And Schema Validation

### 15.1 Rules

Rules:

- Resource payloads validate against Phase 1 models where applicable.
- Tool outputs use typed result models.
- Errors are structured.
- Unknown enum values are not invented by MCP handlers.
- JSON output is canonical where tests compare snapshots.

### 15.2 Media Types

Recommended media types:

- `application/json` for typed payloads.
- `application/schema+json` for schema resources.
- `text/markdown` only for prompt templates when returned as prompt text, not for evidence resources.

### 15.3 Size Limits

Rules:

- Enforce max resource bytes.
- Large payloads become artefact refs.
- Truncated payloads include diagnostics.
- Graph resources return manifests/chunks.

---

## 16. Security And Privacy

### 16.1 Local Server Assumptions

Phase 4 is local-first. It should still avoid unsafe defaults:

- Do not expose absolute paths unless redaction policy allows.
- Do not expose raw full source files through graph resources.
- Do not run network commands.
- Treat task IDs as sensitive.
- Disable broad task listing in unauthenticated multi-user mode.
- Bind task state/results to authorization context where supported.

### 16.2 Argument Redaction

Rules:

- Store argument hashes in telemetry.
- Store full arguments only as redacted artefacts when necessary.
- Resource paths should be repo-relative.
- Error messages should not leak secrets or full local paths by default.

### 16.3 Authorization Boundary

Phase 4 should provide hooks for authorization context:

- Request context identity.
- Task ownership.
- Subscription ownership.
- Resource read authorization.

It does not need to implement enterprise auth.

---

## 17. Development And Test Harness

### 17.1 MCP Client Test Harness

Create a local test harness that can:

- Start server in-process.
- List resources.
- Read resources.
- List tools.
- Call tools.
- Create task-capable tool calls.
- Poll task status.
- Fetch task result.
- Subscribe to resources.
- Capture notifications.
- Retrieve prompts.

### 17.2 Fixture Workspace

Build tests on a fixture workspace containing:

- Registered Python fixture repo.
- Graph manifest.
- Graph slice data.
- Summary cache record.
- Blame-chain record.
- Build evidence record.
- At least one indexing run record.

### 17.3 Regression Fixtures

Store expected snapshots for:

- Tool descriptors.
- Resource descriptors.
- Prompt stubs.
- Permission metadata.
- Basic refusal cases.

---

## 18. Test Plan

### 18.1 Server Tests

Required:

- Server starts.
- Server exposes capabilities.
- Server opens workspace.
- Server handles empty workspace.
- Server handles indexed workspace.
- Server shuts down cleanly.

### 18.2 Resource Tests

Required:

- List resources.
- Read `repos`.
- Read graph schema.
- Read run-record schema.
- Read graph manifest.
- Read graph slice.
- Read symbol summary.
- Read blame chain.
- Read build evidence.
- Invalid URI rejected.
- Too-large resource returns manifest/diagnostic.
- Stale/mixed snapshot metadata preserved.

### 18.3 Tool Tests

Required:

- List tools.
- Tool descriptors include permission metadata.
- `register_repo` works.
- `graph_build` starts task.
- `graph_update` starts task.
- `plugin_reload` returns explicit unavailable/no-op result.
- `get_graph_slice` returns typed slice.
- `find_callers` works on fixture.
- `find_callees` works on fixture.
- `git_blame_chain` returns fixture blame.
- Invalid args rejected.
- Unsafe paths rejected.

### 18.4 Task Tests

Required:

- Task create result.
- Task status polling.
- Task result retrieval.
- Task failure retrieval.
- Task cancellation.
- Task TTL expiration.
- Task restart recovery.
- High-entropy task IDs.
- Authorization binding where supported.
- `tasks/list` policy for single-user and multi-user modes.

### 18.5 Notification Tests

Required:

- Subscribe to resource.
- Invalid subscription rejected.
- `register_repo` emits list-changed.
- `graph_build` completion emits graph update.
- `graph_update` completion emits affected resource updates.
- Missed notification can be recovered by resource reread.

### 18.6 Prompt Tests

Required:

- List prompts.
- Retrieve all public prompt stubs.
- Validate prompt argument schemas.
- Prompt retrieval does not execute workflows.
- Sampling fallback is represented for patch-review prompt.
- Prompt snapshots are stable.

### 18.7 Regression Tests

Required:

- Tool-description snapshot.
- Resource descriptor snapshot.
- Prompt snapshot.
- Permission metadata snapshot.
- Hidden policy/refusal cases.
- Tool-order cases.
- Semantic mutation cases for prompt/tool descriptions where practical.

---

## 19. Work Packages

### P4.1 Server Runtime And Config

Build:

- Server context.
- Config model.
- Startup/shutdown lifecycle.
- Capability descriptor.
- Workspace opening.

Deliverables:

- `mcp_server/server.py`
- `mcp_server/config.py`
- `mcp_server/context.py`
- Startup tests.

Acceptance:

- Server starts against empty and fixture workspaces.

### P4.2 Resource Registry And URI Router

Build:

- Resource descriptor model.
- URI template parser.
- Resource handler registry.
- Common resource result/error model.

Deliverables:

- `mcp_server/resource_registry.py`
- `mcp_server/resource_uris.py`
- Resource registry tests.

Acceptance:

- Resource routes validate and dispatch correctly.

### P4.3 Core Resource Handlers

Build:

- Repos resource.
- Graph schema resource.
- Run-record schema resource.
- Graph manifest resource.
- Graph slice resource.
- Summary resource.
- Blame resource.
- Build-evidence resource.

Deliverables:

- `mcp_server/resources/*.py`
- Resource tests.

Acceptance:

- MCP client can list and read core index resources.

### P4.4 Tool Registry And Permission Descriptors

Build:

- Tool descriptor model.
- Input/output schema binding.
- Permission metadata.
- Tool handler registry.
- Basic refusal helpers.

Deliverables:

- `mcp_server/tool_registry.py`
- `mcp_server/tool_permissions.py`
- Tool descriptor tests.

Acceptance:

- Tools expose required permission metadata.

### P4.5 Graph And Registry Tools

Build:

- `register_repo`.
- `get_graph_slice`.
- `find_callers`.
- `find_callees`.
- `git_blame_chain`.
- `plugin_reload` placeholder.

Deliverables:

- `mcp_server/tools/*.py`
- Tool tests.

Acceptance:

- MCP client can call graph tools and receive typed results.

### P4.6 Task Manager

Build:

- Task ID generation.
- Task store.
- Task runner.
- Task status/result/cancel APIs.
- TTL expiration.
- Restart recovery.
- Task progress records.

Deliverables:

- `mcp_server/tasks.py`
- `mcp_server/task_store.py`
- `mcp_server/task_runner.py`
- Task tests.

Acceptance:

- Long-running `graph_build` can run as a recoverable task.

### P4.7 Task-Capable `graph_build` And `graph_update`

Build:

- Wrap Phase 3 build/update service.
- Emit task progress.
- Store final result artefact.
- Emit resource notifications.
- Link to indexing run records.

Deliverables:

- Task wrappers in graph tool module.
- Integration tests.

Acceptance:

- `graph_build` can be launched, polled, and fetched as a task.

### P4.8 Notifications And Subscriptions

Build:

- Subscription store.
- Resource update notification emitter.
- List-changed notification emitter.
- Notification tests.

Deliverables:

- `mcp_server/notifications.py`
- `mcp_server/subscriptions.py`
- Notification tests.

Acceptance:

- Resource subscriptions and update/list-changed notifications fire for graph, summary, repo, and plugin changes where implemented.

### P4.9 Sampling Capability Detection

Build:

- Sampling capability detection.
- Capability record.
- Harness condition linkage placeholder.
- Fallback metadata for prompts.

Deliverables:

- `mcp_server/sampling.py`
- Sampling tests.

Acceptance:

- Sampling availability is detected and recorded.

### P4.10 Prompt Registry And Public Prompt Stubs

Build:

- Prompt registry.
- Prompt templates.
- Argument schemas.
- Retrieval handler.
- Prompt snapshot tests.

Deliverables:

- `mcp_server/prompts.py`
- `mcp_server/prompts/*.md`
- Prompt tests.

Acceptance:

- Public prompt stubs are retrievable and do not execute workflows.

### P4.11 Telemetry Hooks

Build:

- Tool-call telemetry.
- Task telemetry.
- Run-event linkage when run context exists.
- Redaction-aware argument hashing.

Deliverables:

- `mcp_server/telemetry.py`
- Telemetry tests.

Acceptance:

- MCP tools produce trace events and task events link to run records where available.

### P4.12 Regression Harness

Build:

- Tool-description regression tests.
- Prompt regression tests.
- Permission metadata tests.
- Refusal cases.
- Tool-order cases.

Deliverables:

- `tests/mcp_server/test_tool_description_regressions.py`
- `tests/mcp_server/test_prompt_regressions.py`

Acceptance:

- Prompt/tool-description changes are covered by regression tests or explicit review criteria.

---

## 20. Suggested Implementation Order

Recommended order:

1. Server config and context.
2. Resource registry and URI parsing.
3. Schema and repos resources.
4. Graph manifest/slice, summary, blame, and build-evidence resources.
5. Tool registry and permission descriptors.
6. Read-only graph tools.
7. `register_repo`.
8. Task manager and task persistence.
9. Task-capable `graph_build`.
10. Task-capable `graph_update`.
11. Notifications and subscriptions.
12. Sampling capability detection.
13. Prompt registry and stubs.
14. Telemetry hooks and run-event linkage.
15. Regression harness.

Reasoning:

- Resource reads validate server plumbing before side-effecting tools.
- Read-only tools validate typed results before task infrastructure.
- Task manager should land before wrapping `graph_build`.
- Notifications should be tested against real graph build/update effects.
- Prompt stubs should come after tool/resource descriptors are stable enough to reference.

---

## 21. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 4 |
|---|---|
| Phase 4A - Operational runtime plane | Tool descriptors, telemetry hooks, task/run links, resource notification infrastructure, prompt/tool regression harness |
| Phase 5 - Language backend expansion | Existing graph build/update tools and backend capability reporting through resources/tasks |
| Phase 6 - SARIF/static analysis | Task wrapper pattern, resource routing, SARIF resource notification hooks |
| Phase 7 - Interface plugins | `plugin_reload` surface, list-changed notifications, interface resource extension point |
| Phase 8 - Repo-QA | Graph slice tool/resource and prompt/tool schema conventions |
| Phase 9 - Fault localisation | Graph query tools, summaries, blame, build evidence |
| Phase 10 - Evaluation harness | Task pattern, prompt/tool regression harness, schema resources |
| Phase 11 - Patch review | Sampling capability record, prompt stubs, graph query tools |
| Phase 12 - SAST repair | Task-capable tool conventions and future SARIF resource routing |
| Phase 13 - Bug-resolve | Prompt stub, task lifecycle, resource reads, tool telemetry |
| Phase 14 - Implementation-check | Prompt stub, schema resources, graph resources, task pattern |
| Phase 15 - Blast radius | Graph slice and callers/callees tools |
| Phase 16 - Dynamic traces | Task lifecycle and notification infrastructure |
| Phase 17 - Memory | Resource subscription hooks and future memory resource route pattern |
| Phase 18 - Release gates | Tool/prompt regression tests and task/harness condition recording |
| Phase 19 - Distribution | Server runtime, dev command, task restart recovery, resource size limits |

---

## 22. Exit Criteria Mapping

Source Phase 4 exit criterion:

- MCP client can list resources and call graph tools.

Concrete acceptance:

- Test MCP client lists core resources.
- Test MCP client reads `repos`, schemas, graph manifest, graph slice, summary, blame, and build evidence.
- Test MCP client calls `get_graph_slice`, `find_callers`, `find_callees`, and `git_blame_chain`.

Source Phase 4 exit criterion:

- Long-running `graph_build` can run as a task.

Concrete acceptance:

- `graph_build` returns task create result.
- Task can be polled.
- Task result can be fetched.
- Task progress is persisted.
- Task failure and cancellation are observable.

Source Phase 4 exit criterion:

- Resource subscriptions and update/list-changed notifications fire for graph, summary, repo, and plugin changes.

Concrete acceptance:

- `register_repo` emits list-changed.
- `graph_build` emits graph/build-evidence updates.
- `graph_update` emits graph/summary/blame/build-evidence updates.
- `plugin_reload` emits only appropriate placeholder or actual list-changed behavior.

Source Phase 4 exit criterion:

- MCP tools expose permission metadata and produce trace events.

Concrete acceptance:

- Every tool descriptor includes required mode, path scope, network requirement, side-effect class, and approval requirement.
- Tool calls record telemetry with redaction status.

Source Phase 4 exit criterion:

- Task events are linked to run records where a workflow/task run exists.

Concrete acceptance:

- `graph_build` task links to Phase 3 indexing run ID when available.
- If called inside a run context, tool/task events append to that run.

Source Phase 4 exit criterion:

- Task IDs are high-entropy, TTL-bound, and recoverable after server restart within policy.

Concrete acceptance:

- Task ID tests check non-predictability.
- TTL expiration works.
- Restart recovery test covers queued/running/completed tasks.

Source Phase 4 exit criterion:

- Sampling capability is detected and recorded in the Harness Condition Sheet.

Concrete acceptance:

- Capability detection result is stored in server capability metadata and available for Harness Condition Sheet capture.

Source Phase 4 exit criterion:

- Prompt/tool-description changes are covered by regression tests or explicit review criteria.

Concrete acceptance:

- Prompt snapshots and tool descriptor snapshots exist.
- Refusal and policy-compliance cases are tested.

---

## 23. Definition Of Done

Phase 4 is done when:

- The `code-intelligence` MCP server starts against an `evidence-sca` workspace.
- An MCP client can list and read core index resources.
- Schema resources serve Phase 1 JSON Schema exports.
- Graph resources return manifests/slices with snapshot and provenance metadata.
- Summary, blame, and build-evidence resources are routable.
- Tool registry exposes Phase 4 tools with permission metadata.
- Read-only graph tools return typed results.
- `register_repo` updates the registry and emits list-changed.
- `graph_build` and `graph_update` can run as task-capable tools.
- Task IDs are high-entropy, TTL-bound, persisted, and recoverable after restart within policy.
- Task polling, result retrieval, cancellation, failure, and expiration are tested.
- Resource subscriptions and notifications work for repo, graph, summary, blame, and build-evidence changes.
- Sampling capability is detected and recorded.
- Public prompt stubs are retrievable and do not execute workflows.
- Tool calls and task progress emit trace events.
- Prompt/tool-description regression tests cover descriptors, permission metadata, refusals, and prompt stubs.

---

## 24. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| MCP handlers return prose instead of typed payloads | Later workflows cannot audit evidence | Validate resource/tool outputs against Phase 1 models and result schemas |
| Full graph resource dumps too much data | Clients overload or leak context | Always return graph manifest/chunk refs for full graph; use slices for bounded context |
| Task IDs are predictable | Local task results leak across users | Use high-entropy IDs, TTLs, and auth-context binding where supported |
| Notifications are treated as authoritative | Clients miss updates or hold stale state | Persist store state and require clients to reread resources after notifications |
| Prompt stubs accidentally imply workflows are implemented | Users overtrust incomplete functionality | Prompt stubs must state launcher availability and return plans, not verdicts |
| Sampling is assumed available | Patch-review and future workflows break on clients without Sampling | Detect Sampling and expose fallback metadata |
| Permission descriptors are incomplete | Phase 4A policy engine lacks stable inputs | Descriptor tests require mode, path scope, network, side-effect, and approval fields |
| Task restart recovery corrupts state | Long-running builds appear completed incorrectly | Mark in-flight tasks after restart according to explicit recovery policy and preserve diagnostics |
| Tool-description changes silently weaken policy | Regression in client behavior or safety | Snapshot descriptors and add hidden policy/refusal cases |

---

## 25. Phase 4 Completion Report Template

When Phase 4 implementation is complete, report:

```text
Phase 4 completion report

Implemented:
- MCP server runtime:
- Resource registry:
- Core resource handlers:
- Tool registry:
- Graph tools:
- Task manager:
- graph_build task:
- graph_update task:
- Notifications/subscriptions:
- Sampling capability detection:
- Prompt registry/stubs:
- Telemetry hooks:
- Regression harness:

Verification:
- Server startup tests:
- Resource tests:
- Tool tests:
- Task tests:
- Notification tests:
- Prompt tests:
- Regression tests:
- Local verify command:

Exit criteria:
- MCP client lists resources and calls graph tools:
- graph_build runs as task:
- resource subscriptions and notifications fire:
- tools expose permission metadata and trace events:
- task events link to run records where available:
- task IDs high-entropy, TTL-bound, restart-recoverable:
- Sampling capability recorded:
- prompt/tool-description changes covered:

Known limitations:
-

Follow-up for Phase 4A:
-
```

---

## 26. Minimal First Slice Within Phase 4

If Phase 4 needs to be split further, implement this first:

1. MCP server startup and capability descriptor.
2. Resource registry and URI parser.
3. `code-intelligence://repos`.
4. `code-intelligence://schema/graph.schema.json`.
5. `code-intelligence://schema/run-record.schema.json`.
6. `code-intelligence://graph/{repo}` manifest resource.
7. `code-intelligence://graph/slice/{repo}/{files}` resource.
8. Tool registry with permission descriptors.
9. `get_graph_slice`.
10. `register_repo`.
11. Minimal task manager.
12. Task-capable `graph_build`.
13. Resource update/list-changed notifications for repo and graph.
14. Prompt registry with all five public prompt stubs.

This minimal slice makes the indexed evidence usable by MCP clients and unblocks Phase 4A, Phase 5, and Phase 6 without pretending that high-level audit/repair workflows are ready.

