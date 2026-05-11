# SKILL: architecture-compliance

Check whether the current implementation fully and correctly satisfies all
features and functions defined in a design/architecture document.

> **MANDATORY — DO NOT SKIP:** This skill MUST be executed by invoking the
> `code-intelligence` MCP server (`uv run llm-sca-tooling mcp serve`) and
> calling its tools.  You MUST NOT:
> - Read the architecture doc and write code checks manually.
> - Import Python modules directly as a substitute for MCP tool calls.
> - Use any external agent harness tool (`local-agent-harness`, etc.) as a
>   proxy for `run_implementation_check`.
> Skipping or bypassing these steps defeats the purpose of this repository.

---

## When to use

- User says: "check if features/functions are fully implemented"
- User says: "audit implementation completeness against the design doc"
- User says: "are all architecture requirements satisfied?"
- User says: "use the skills and MCP server to investigate"

---

## How to start the MCP server

```bash
# stdio transport (recommended for agents)
uv run llm-sca-tooling mcp serve --transport stdio
```

Initialize the MCP session (send this JSON-RPC frame on stdin):

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

---

## Workflow steps

### Step 1 — Verify server is ready

```json
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://repos"},"id":2}
```

Expected: list of registered repos. If empty, proceed to Step 2.

### Step 2 — Register the target repository

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_id":"llm-sca-tooling","path":"."}},"id":3}
```

### Step 3 — Build the graph index

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo":"llm-sca-tooling"}},"id":4}
```

### Step 4 — Run implementation check against the architecture doc

Pass the FULL content of `docs/llm-sca-tooling-architecture.md` as the
`spec` argument:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full_content_of_architecture_doc>"}},"id":5}
```

Alternatively, pass individual feature sections to get per-feature verdicts.

### Step 5 — Retrieve per-clause verdicts

Read the report from the response payload:
- `report.satisfied_clauses` — fully implemented
- `report.violated_clauses` — NOT implemented or incorrect
- `report.unknown_clauses` — inconclusive (require manual review)
- `report.overall_verdict` — `compliant` / `partially_compliant` / `non_compliant`

### Step 6 — For each violated/unknown clause

Run targeted static analysis:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo":"llm-sca-tooling","predicate":"<clause_text>"}},"id":6}
```

And fetch relevant files:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"repo":"llm-sca-tooling","query":"<clause_text>"}},"id":7}
```

### Step 7 — Run readiness audit

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"llm-sca-tooling"}},"id":8}
```

### Step 8 — Emit a structured report

Report with per-clause verdicts, evidence, and a recommendation:
- `compliant` → all features implemented
- `partially_compliant` → list each unimplemented feature with clause ID
- `non_compliant` → list all violations with file references

---

## Verify Gate

```
make verify                  # full verify gate — must exit 0
run_implementation_check     # overall_verdict must be "compliant"
run_readiness_audit          # no per-axis regression
```

---

## Completion Criteria

- `run_implementation_check` was called via MCP JSON-RPC (not Python import).
- A run record exists for the check: `code-intelligence://runs/{run_id}`.
- Per-clause verdicts are recorded with confidence and provenance.
- `make verify` exits 0.
- Final report emitted with satisfied/violated/unknown clause lists.

---

## Notes

- The MCP tool parameter name is `spec` (not `design_ref`).
- Pass the full text of the design document, not just the filename.
- `violated_clauses` and `unknown_clauses` both require follow-up.
- For any clause marked `unknown`: use `capture_trace` for dynamic evidence.
- Record lessons in `.agent/lessons/` after a successful compliance run.
