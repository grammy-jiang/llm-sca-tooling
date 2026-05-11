---
name: architecture-compliance
description: >
  Check whether the current codebase fully and correctly implements all features
  and functions defined in a design or architecture document. Use when asked to
  audit implementation completeness against the design doc, check if features or
  functions are fully implemented, verify all architecture requirements are satisfied,
  or investigate with the skills and MCP server. ALWAYS invoke the llm-sca-tooling
  MCP server — never read the architecture doc and write checks manually, never
  use Python imports directly, and never substitute external harness tools.
compatibility: >
  Requires Python 3.12+, uv, and the llm-sca-tooling package installed in the
  current repository. MCP server must be started before any tool calls:
  `uv run llm-sca-tooling mcp serve --transport stdio`
license: MIT
metadata:
  mcp-server: llm-sca-tooling
  mcp-transport: stdio
  version: "1.0.0"
---

# architecture-compliance

> **MANDATORY — DO NOT SKIP:**
> This skill MUST be executed by invoking the `llm-sca-tooling` MCP server and
> calling its tools via JSON-RPC. You MUST NOT:
> - Read the architecture doc and write code checks manually
> - Import Python modules directly as a substitute for MCP tool calls
> - Use `local-agent-harness` or any external tool instead of `run_implementation_check`
>
> Bypassing these steps defeats the purpose of this repository and is a policy violation.

## Step 1 — Start the MCP server

```bash
uv run llm-sca-tooling mcp serve --transport stdio
```

Initialize (send on stdin):

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"agent","version":"1"}},"id":1}
```

## Step 2 — Register the repository

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_id":"llm-sca-tooling","path":"."}},"id":2}
```

## Step 3 — Build graph index

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo":"llm-sca-tooling"}},"id":3}
```

## Step 4 — Run implementation check

Pass the FULL content of the architecture document as `spec`:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full_content_of_architecture_doc>"}},"id":4}
```

Read the response:
- `report.satisfied_clauses` — fully implemented
- `report.violated_clauses` — NOT implemented or incorrect
- `report.unknown_clauses` — inconclusive (require manual review)
- `report.overall_verdict` — `compliant` / `partially_compliant` / `non_compliant`

## Step 5 — Investigate violated/unknown clauses

For each violated or unknown clause, call both:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo":"llm-sca-tooling","predicate":"<clause_text>"}},"id":5}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"repo":"llm-sca-tooling","query":"<clause_text>"}},"id":6}
```

## Step 6 — Run readiness audit

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"llm-sca-tooling"}},"id":7}
```

## Step 7 — Emit structured report

- `compliant` → all features implemented
- `partially_compliant` → list each unimplemented feature with clause ID and file evidence
- `non_compliant` → list all violations with file references

---

## Verify Gate

```
make verify                  # must exit 0
run_implementation_check     # overall_verdict must be "compliant"
run_readiness_audit          # no per-axis regression
```

## Completion Criteria

- `run_implementation_check` called via MCP JSON-RPC (not Python import)
- Run record exists: `code-intelligence://runs/{run_id}`
- Per-clause verdicts recorded with confidence and provenance
- `make verify` exits 0
- Final report emitted with satisfied/violated/unknown clause lists

## Notes

- The MCP tool parameter is `spec` (not `design_ref`)
- Pass the full document text, not a filename
- For `unknown` clauses: use `capture_trace` for dynamic evidence
- See `references/clause-examples.md` for sample clause analysis patterns
