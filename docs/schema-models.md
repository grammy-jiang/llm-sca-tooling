# Phase 1 schema models

This package implements the Phase 1 shared schema and evidence contracts for
LLM-assisted static code analysis tooling.

The models are contract-only. They define typed payloads for graph facts,
evidence, verdicts, run records, operational events, governance, harness
conditions, readiness reports, incidents, memory references, and supply-chain
provenance. They do not implement graph storage, indexing, MCP routing, LLM
calls, tracing backends, or workflow orchestration.

Key invariants:

- Durable facts carry provenance, repository, and snapshot context.
- Confidence is separate from evidence strength.
- LLM-derived evidence cannot claim hard static or hard dynamic strength.
- `unknown` is a first-class verdict when evidence is missing, stale, mixed, or
  operationally incomplete.
- Run events are sequence-numbered, redaction-aware, and validated against their
  owning run.
- JSON Schema exports are generated from the Python models and checked in under
  `schemas/`.

Regenerate schema exports with:

```bash
python -m llm_sca_tooling.schemas.json_schema
```
