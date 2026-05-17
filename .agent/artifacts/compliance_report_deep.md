# Compliance Report — Deep Research Pipeline Audit

**Date**: 2026-05-13
**Session**: fae14089-cea5-466e-b430-29f2a1a96eff
**Repo**: `/home/grammy-jiang/projects/research-pipeline`
**Design docs checked**: 16 (research report + 10 plan documents + 5 sysarch chunks)
**Source artifacts**: `deep_03_all_impl_checks.json`, `deep_04_clause_investigation.json`, `deep_06_readiness.json`

---

## Compliance Summary

- **overall_verdict**: partially_compliant
- **satisfied_clauses**: 1788
- **violated_clauses**: 0
- **unknown_clauses**: 82
- **readiness_stage**: S3
- **ai_readiness_score**: 22 (from `deep_06_readiness.json: report.ai_readiness_score`)

---

## Confirmed Gaps

These gaps were confirmed by direct source inspection after `get_relevant_files`
returned no results for the feature names (all queries returned empty `files` array
in the MCP response).

### GAP-R1: AgentDiversityConfig — Missing

- **clause_id**: clause:99c12c582d9e (deep-research-multi-agent-reliability-plan)
- **summary**: `AgentDiversityConfig` model with `min_model_families` field and
  family_assignment mapping is not present in any source file. The config schema
  has no `[agents.diversity]` section.
- **evidence**: `grep -rn "AgentDiversityConfig\|min_model_families" src/` → exit 1
  (no matches in codebase as of v0.17.12)
- **confidence**: 0.95

### GAP-R2: PreCommitmentPolicy Enum — Missing

- **clause_id**: clause:f5133cf111b2 (deep-research-multi-agent-reliability-plan)
- **summary**: `PreCommitmentPolicy` enum (PARALLEL/SEQUENTIAL_BLIND/SEQUENTIAL_INFORMED)
  not present. `evaluation/pre_commitment.py` exists with `ProtocolState` and
  `ReconciliationStrategy` enums, but `PreCommitmentPolicy` dispatch enum is absent.
- **evidence**: `grep -rn "PreCommitmentPolicy" src/` → exit 1
- **confidence**: 0.95

### GAP-R3: SubAgentBudget — Missing

- **clause_id**: clause:ab8e9c103388 (deep-research-multi-agent-reliability-plan)
- **summary**: `SubAgentBudget` class with `max_tokens`/`target_tokens`/`penalty_above_target`
  fields is not present. No per-sub-agent token budget enforcement or configuration.
- **evidence**: `grep -rn "SubAgentBudget\|max_tokens.*target_tokens" src/` → no matches
- **confidence**: 0.95

### GAP-R4: MinorityFinding in Synthesis Output — Missing

- **clause_id**: clause:5d898fa78db1 (deep-research-multi-agent-reliability-plan)
- **summary**: `MinorityFinding` data model and `minority_findings` field in
  `SynthesisOutput` not present. `synthesis.py` has `_detect_dissent()` function
  but does not emit structured `MinorityFinding` objects.
- **evidence**: `grep -rn "MinorityFinding\|minority_findings" src/` → exit 1
- **confidence**: 0.90

### GAP-M1: between_stages Hook — Missing

- **clause_id**: clause:700d7f4954f1 (deep-research-memory-system-integration-plan)
- **summary**: `between_stages()` lifecycle hook is not wired into the pipeline
  orchestrator. The design specifies this hook should fire at every stage boundary
  to allow memory transitions. `memory/` package exists but is not integrated into
  pipeline execution.
- **evidence**: `grep -rn "between_stages" src/` → 0 matches
- **confidence**: 0.95

---

## Assumptions and Uncertainties

These clauses were marked `unknown` in the implementation check but appear to be
partially or fully implemented based on direct source inspection. The MCP graph
likely returns `unknown` due to naming differences or complex call graphs.

- **clause_id**: multiple (40 from research report, 25 from sysarch)
  - **why_uncertain**: Broad architectural concepts (e.g., "multi-agent reliability",
    "memory lifecycle") are expressed through multiple modules rather than single
    symbols. The MCP graph cannot always trace the connection between a design
    clause and its distributed implementation.
  - **assumption**: true
  - **note**: Blinding audit (`cmd_blinding_audit.py`), dual metrics (`cmd_dual_metrics.py`),
    CBR memory (`memory/cbr.py`), user feedback (`tools.py:record_feedback`),
    and pre-commitment (`evaluation/pre_commitment.py`) ARE implemented.

---

## Readiness Blockers

From `deep_06_readiness.json`:
- **harness_stage**: S3 (production-ready harness)
- **ai_readiness_score**: 22
- **drift_findings**: [] (none)
- **missing_gates**: [] (none)
- **absent_scanners**: [] (none)
- No per-axis blockers from readiness audit

---

## Next Steps

**Status**: partially_compliant → transition to bug-resolve for each confirmed gap.

Gaps to fix (ordered by severity):

1. **GAP-R1** — Add `AgentDiversityConfig` to config schema + validation
2. **GAP-R2** — Add `PreCommitmentPolicy` enum to `evaluation/pre_commitment.py`
3. **GAP-R3** — Add `SubAgentBudget` class + default budgets
4. **GAP-R4** — Add `MinorityFinding` model to synthesis output schema
5. **GAP-M1** — Wire `between_stages()` hook in pipeline orchestrator

After all fixes:
- Re-run `run_implementation_check` to confirm closure
- Run `release` skill for v0.17.13
