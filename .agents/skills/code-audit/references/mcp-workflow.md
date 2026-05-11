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
`get_relevant_files`, `retrieve_memory`, `answer_repo_question`.

## Register repository

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_repo","arguments":{"repo_id":"llm-sca-tooling","path":"."}},"id":3}
```

## Build graph index

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"graph_build","arguments":{"repo":"llm-sca-tooling"}},"id":4}
```

## Run implementation check

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_implementation_check","arguments":{"spec":"<full spec text>"}},"id":5}
```

Response fields: `report.satisfied_clauses`, `report.violated_clauses`,
`report.unknown_clauses`, `report.overall_verdict`
(`compliant` / `partially_compliant` / `non_compliant`).

## Run static analysis

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_static_analysis","arguments":{"repo":"llm-sca-tooling","predicate":"<clause_or_rule>"}},"id":6}
```

## Get relevant files

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_relevant_files","arguments":{"repo":"llm-sca-tooling","query":"<topic>"}},"id":7}
```

## Run readiness audit

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"run_readiness_audit","arguments":{"repo":"llm-sca-tooling"}},"id":8}
```

## Classify patch risk

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"classify_patch_risk","arguments":{"diff":"<unified_diff>"}},"id":9}
```

Allowed risk classes for merge: `safe`, `correct-but-overfit`.
Block on: `vulnerable`, `vulnerability-introducing`.

## Read resources

```json
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://repos"},"id":10}
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://runs/latest"},"id":11}
{"jsonrpc":"2.0","method":"resources/read","params":{"uri":"code-intelligence://readiness/llm-sca-tooling"},"id":12}
```
