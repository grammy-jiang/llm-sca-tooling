# Implementation-Check Workflow

The `run_implementation_check` MCP tool runs Phase 14's seven-stage
implementation-check DAG against a Markdown specification and returns an
`ImplementationCheckReport` together with a `ClauseVerdictMatrix`.

## Stages

1. **Spec ingestion** — parse the Markdown spec, compute a content hash, and
   persist a `SpecDocument` with provenance.
2. **Clause extraction & harness-policy detection** — split obligation
   sentences (must / shall / should / must never / shall not) into atomic
   `Clause` records, mark compound clauses non-atomic, attach risk class, and
   upgrade harness-related obligations to `HarnessPolicyClause`.
3. **Intent graph** — build an `IntentGraph` of intent nodes plus
   `decomposes_to` edges from parent compound clauses to atomic sub-clauses.
4. **Contract generation** — produce `ContractArtifact`s via a pluggable
   `ContractArtifactGenerator` (Null adapter for Phase 14; Semgrep / pytest
   stubs available for downstream use).
5. **Grounding** — link each clause to symbols, files, or repo-QA references
   via `ClauseGrounding`. Ungrounded clauses are flagged.
6. **Static verdict (Stage 5)** — evaluate contracts, SARIF alerts, tests,
   and graph-path evidence into `StaticVerdictRecord`. Failed compiles stay
   diagnostic. Missing harness gates surface as synthetic SARIF alerts.
7. **Soft probes (Stage 6a) & dynamic hook (Stage 6b)** — run the soft
   repo-QA probe (security clauses cannot be auto-passed) and the dormant
   dynamic-trace hook.
8. **Aggregation (Stage 7)** — combine evidence with hard violations
   dominating, soft consensus, and the auto-pass gate (ECE ≤ 0.10 and not
   security/compliance) into `ClauseVerdictRecord`. Assemble the
   `ClauseVerdictMatrix` and the final `ImplementationCheckReport`.

## Hard rules

- Stage 5 violated verdicts can never be overridden by Stage 6a / 6b soft
  evidence.
- Security and compliance clauses cannot be marked `satisfied` solely from
  soft repo-QA evidence; they remain `unknown` without hard evidence.
- The auto-pass gate is closed when calibration ECE is missing or > 0.10
  and for high-stakes risk classes.
- Ungrounded clauses default to `unknown` with `ungrounded_reason` recorded.
- Every report carries a `harness_condition_id` and a stable `report_id`.

## Recommendation mapping

| Overall verdict | Recommendation |
|---|---|
| compliant | merge-supporting |
| non_compliant | block |
| partially_compliant | review-required |
| unknown | unknown |

Always cite `report.report_id` and `report.harness_condition_id` in any
reply, and surface the per-stage evidence (`stage_5_verdicts`,
`stage_6a_verdicts`, `stage_6b_verdict`) when justifying a non-compliant or
unknown outcome.
