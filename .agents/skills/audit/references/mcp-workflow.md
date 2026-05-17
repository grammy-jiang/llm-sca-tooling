# MCP Workflow Reference — code-audit

Full JSON-RPC 2.0 frame examples for the `llm-sca-tooling` stdio server.

## Session initialization

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

## List available tools

```json
{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}
```

Key tools: `register_repo`, `graph_build`, `run_implementation_check`,
`run_static_analysis`, `run_issue_resolution`, `run_patch_review`,
`run_readiness_audit`, `classify_patch_risk`, `capture_trace`,
`get_relevant_files`, `retrieve_memory`, `answer_repo_question`,
`task_status`, `task_result`.

## Register repository

> **`repo_path` is required** (not `path`, not `repo_id`). Provide an absolute filesystem
> path. A relative `"."` resolves from the server's working directory, which may differ
> from the target repo. The response contains `payload.repo.repo_id` — note this for
> subsequent `graph_build` calls.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":3}
```

## Build graph index (async)

> **`graph_build` requires `repo_path` (absolute path) or `repo_id`** (the ID returned
> by `register_repo`). **Not** `repo`. This call is async: it returns `"status":"accepted"`
> with a `task_id`. You MUST poll `task_status` then `task_result` before proceeding.

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo_path":"/absolute/path/to/repo"}},"id":4}
```

### Async polling loop for graph_build (and other async tools)

After receiving `{"status":"accepted","task":{"task_id":"<id>",...}}`:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_status","arguments":{"task_id":"<task_id>"}},"id":5}
```

Repeat until `task.status` == `"completed"` (or `"failed"`). Then fetch results:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"task_result","arguments":{"task_id":"<task_id>"}},"id":6}
```

The same polling pattern applies to `run_patch_review` when called with `"task":true`.

## Run implementation check

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full spec text>"}},"id":7}
```

Response fields: `report.satisfied_clauses`, `report.violated_clauses`,
`report.unknown_clauses`, `report.overall_verdict`
(`compliant` / `partially_compliant` / `non_compliant`).

## Run issue resolution (bug-resolve context)

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_issue_resolution","arguments":{"issue_text":"<bug description or clause text>"}},"id":8}
```

## Run static analysis

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo":"<repo_path_or_id>","predicate":"<clause_or_rule>"}},"id":9}
```

## Get relevant files

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"repo":"<repo_path_or_id>","query":"<topic>"}},"id":10}
```

## Run readiness audit

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"<repo_path_or_id>"}},"id":11}
```

## Run patch review

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_patch_review","arguments":{"diff":"<unified_diff>"}},"id":12}
```

## Classify patch risk

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_patch_risk","arguments":{"diff":"<unified_diff>"}},"id":13}
```

Allowed risk classes for merge: `safe`, `correct-but-overfit`.
Block on: `vulnerable`, `vulnerability-introducing`.

## Read resources

```json
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://repos"},"id":14}
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://runs/latest"},"id":15}
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://readiness/<repo_path_or_id>"},"id":16}
```

Use `code-intelligence://runs/latest` to confirm the run record URI after each workflow.

## Parameter quick-reference

| Tool | Required params | Notes |
|---|---|---|
| `register_repo` | `repo_path` | Absolute or relative-to-server path. Returns `payload.repo.repo_id`. |
| `graph_build` | `repo_path` OR `repo_id` | **Async** — poll `task_status` → `task_result`. |
| `run_implementation_check` | `spec` | Full spec text, not a filename. |
| `run_issue_resolution` | `issue_text` | Bug description or failing clause text. |
| `run_patch_review` | `diff` | Unified diff string. Optionally `"task":true` for async. |
| `classify_patch_risk` | `diff` | Same unified diff. |
| `run_static_analysis` | `repo`, `predicate` | `repo` accepts path or registered ID. |
| `get_relevant_files` | `repo`, `query` | `repo` accepts path or registered ID. |
| `run_readiness_audit` | `repo` | `repo` accepts path or registered ID. |
| `task_status` | `task_id` | Poll this for any async tool. |
| `task_result` | `task_id` | Fetch after `task_status` shows `completed`. |
