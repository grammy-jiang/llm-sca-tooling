# Clause Analysis Reference — architecture-compliance

## Sample clause patterns for `run_implementation_check`

### Passing a full architecture doc section

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "run_implementation_check",
    "arguments": {
      "spec": "## F1 — Static Analysis Engine\nThe tooling SHALL provide a static analysis engine that...\n[rest of section]"
    }
  },
  "id": 4
}
```

### Passing individual feature clauses for fine-grained verdicts

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "run_implementation_check",
    "arguments": {
      "spec": "F1.1: The engine SHALL support Semgrep rules for Python, JavaScript, TypeScript, C, and C++."
    }
  },
  "id": 5
}
```

## Interpreting verdicts

| Verdict | Meaning | Action |
|---|---|---|
| `compliant` | All clauses satisfied | Record run, close investigation |
| `partially_compliant` | Some clauses unknown/violated | Investigate each gap, file issues |
| `non_compliant` | Multiple violations | Escalate, create fix plan |

## Unknown clause follow-up

When a clause is `unknown`, use `capture_trace` to gather dynamic evidence:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "capture_trace",
    "arguments": {
      "script": "python -c \"from llm_sca_tooling.<module> import <symbol>; print(<symbol>.__doc__)\""
    }
  },
  "id": 10
}
```

## Reading the run record

After `run_implementation_check` completes, read the run record:

```json
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://runs/latest"},"id":11}
```

## Architecture doc location

The primary architecture doc for this repository is:
`docs/llm-sca-tooling-architecture.md`

Pass its full content to `run_implementation_check` for a complete compliance check.
