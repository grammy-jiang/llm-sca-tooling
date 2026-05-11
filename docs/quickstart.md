# Quickstart Guide

> This guide walks through the five most common workflows in under 10 minutes.
> Prerequisites: `evidence-sca` installed and `llm-sca-tooling config validate` exits 0.
> See [Installation Guide](installation.md) if you haven't installed yet.

---

## Limitations

- Results are evidence-graded, not guaranteed correct. Every finding has a confidence
  level (`parser > analyser > heuristic > unknown`). Review findings accordingly.
- LLM-assisted workflows (bug resolve, patch review, implementation check) require an
  LLM API key. Null-mode runs use heuristics only and are suitable for CI smoke checks.
- A `HarnessConditionSheet` must be completed before any run can be accepted as a
  quality-verified result. See [Harness Setup Guide](harness-setup-guide.md).
- The MCP server operates locally. For remote multi-client deployments, see
  [Installation Guide — HTTP transport](installation.md#streamable-http-transport).

---

## Step 1: Register a Repository

```bash
cd /path/to/your/repo
llm-sca-tooling mcp start &    # start MCP server (background)
# Then via your MCP client, or via CLI wrapper:
# register_repo(repo_path=".", name="my-repo")
```

Or use the MCP tool directly from your LLM client:
```
register_repo(repo_path="/path/to/your/repo", name="my-repo")
```

Expected result: `{ "status": "registered", "repo_id": "..." }`

---

## Step 2: Build the Graph Index

```bash
# Via MCP tool:
graph_build(repo_path="/path/to/your/repo")
```

This indexes all source files using `universal-ctags` and builds the code graph.
Large repositories (>10 000 files) are automatically chunked.

Check progress:
```
task_status(task_id="<task_id from graph_build>")
task_result(task_id="<task_id>")
```

Expected result: `{ "status": "complete", "node_count": N, "edge_count": M }`

---

## Step 3: Query a Graph Slice

Once the graph is built, retrieve a subgraph around a symbol:

```
get_graph_slice(repo_path="/path/to/your/repo", symbol="MyClass", depth=2)
```

Expected result: a JSON graph with nodes (functions, classes, files) and edges (calls, imports).

---

## Step 4: Run the Bug-Resolve Workflow

Given an issue description, `run_issue_resolution` produces a structured resolution report:

```
run_issue_resolution(
    repo_path="/path/to/your/repo",
    issue_text="NullPointerException in UserService.authenticate when user is None",
    run_id="my-run-001"
)
```

Check result via:
```
task_result(task_id="<task_id>")
```

The report includes:
- Evidence nodes (functions, call sites, test coverage gaps)
- Proposed resolution steps with confidence levels
- Risk grade and blast radius estimate
- `HarnessConditionSheet` reference

---

## Step 5: View Harness Status and Run a Release Gate

Check the harness readiness:
```bash
llm-sca-tooling harness status
```

Run the T1 smoke release gate:
```bash
llm-sca-tooling release gate --suite t1 --null-mode
```

Run the full release gate (requires all prior phase artefacts):
```bash
llm-sca-tooling release gate --suite all --operational-gate-required
```

---

## Replay a Run

To inspect a previous run's event sequence:
```bash
llm-sca-tooling replay run <run_id> --show-events
llm-sca-tooling replay run <run_id> --output-format json > run-events.json
```

To compare two runs:
```bash
llm-sca-tooling replay run <run_id_a> --diff-run <run_id_b>
```

---

## Common Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `graph_build` fails with ctags error | `universal-ctags` not installed | `brew install universal-ctags` or `apt install universal-ctags` |
| `config validate` exits 1 | Missing workspace directory | `mkdir -p ~/.evidence-sca` |
| `release gate` exits 1 | T1 smoke eval failing | Run with `--null-mode`; review calibration report |
| MCP tools return `unknown` evidence | Graph not built or stale | Re-run `graph_build` |
| `harness status` reports S0 | AGENTS.md missing | See [Harness Setup Guide](harness-setup-guide.md) |

---

## Next Steps

- [Architecture Overview](architecture.md) — understand the five product surfaces.
- [Evaluation Guide](evaluation-guide.md) — run T1-T4 benchmarks and interpret calibration reports.
- [Plugin Authoring Guide](plugin-authoring-guide.md) — extend the tool to new languages.
- [Harness Setup Guide](harness-setup-guide.md) — configure governance and permission profiles.
- [Incident Response Guide](incident-response-guide.md) — respond to operational incidents.
