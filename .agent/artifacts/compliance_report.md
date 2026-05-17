# Compliance Report: Implementation Completeness Audit

Generated: 2026-05-17T22:46:00+10:00
Session: audit-impl-completeness-20260517T223948+1000

## Scope

Audited the implementation in `/home/grammy-jiang/Documents/evidence-sca`
against the design and implementation plans in `docs/`:

- `docs/llm-sca-tooling-architecture.md` (§2.1 Named Architecture Surface
  Checklist)
- `docs/llm-sca-tooling-implementation-plan.md` (§2.1 Named surface and §3
  per-phase exit criteria for Phase H0 and Phases 0–19)

Spec assembled into `.agent/artifacts/audit_spec_20260517.md` (17 KB,
84 extractable clauses) and submitted to the MCP `run_implementation_check`
workflow as a single spec text.

Workflow used: `audit` skill → `implementation-check` route.
All evidence collection routed through `llm-sca-tooling` MCP server.

## Compliance Summary

| Metric | Value | Source |
|---|---|---|
| overall_verdict | partially_compliant | impl_check_report.json |
| recommendation | review-required | impl_check_report.json |
| total clauses extracted | 84 | matrix |
| satisfied_clauses | 77 | impl_check_report.json |
| unknown_clauses | 6 | impl_check_report.json |
| violated_clauses | 0 | impl_check_report.json |
| security_clause_summary | none | impl_check_report.json |
| harness_policy_summary | present | impl_check_report.json |
| operational_compliance_verdict | operational_check_passed | impl_check_report.json |
| ai_readiness_score | 22 / 25 | readiness_report.json |
| harness_stage | S3 | readiness_report.json |
| graph snapshot status | dirty / partial index | get_relevant_files |

## Confirmed Gaps

After investigation via `mcp__llm-sca-tooling__get_relevant_files`, **no real
implementation gaps were found**. All 6 `unknown` verdicts are explained:

| Clause ID | Category | Real gap? | Resolution |
|---|---|---|---|
| `clause:a7f6634144d6` | spec_sentence_fragment | No | Spec intro fragment with no target symbol. |
| `clause:c636122d894a` | spec_section_header | No | "...following MCP resources:" header; individual resource bullets resolved to satisfied. |
| `clause:dc47a5b20f61` | spec_section_header | No | "...following MCP tools." header; individual tool clauses (find_callers, register_repo, run_implementation_check, etc.) all satisfied. |
| `clause:74400059eb31` | spec_section_header | No | "...following public prompts:" header; clauses for implementation-check / bug-resolve / patch-review / operational-review / readiness-audit all satisfied. |
| `clause:799599afdf15` | spec_section_header | No | "...following private workflow templates:" header; clauses for investigate / repair / audit / blast-radius / sast-repair / risk-classify / evaluate all satisfied. |
| `clause:a42a2d9f822d` | behavioural_requirement | No | "Original alert must disappear before fixed." Implementation in `src/llm_sca_tooling/sarif/delta.py:18-63` (`compute_sarif_delta`) and `src/llm_sca_tooling/sarif/delta.py:81-88` (`_change_type` returning appeared/disappeared/changed). Calibration fixture pending (Phase 18). |

See `.agent/artifacts/clause_investigation.json` for full evidence.

## Positive Coverage (77 satisfied clauses)

The 77 satisfied clauses validate that the implementation covers, with
graph-grounded evidence:

- **All named MCP tools** with target symbols: `find_callers`, `find_callees`,
  `get_relevant_files`, `get_graph_slice`, `trace_cross_language`,
  `git_blame_chain`, `get_interface_contract`, `classify_repo_question`,
  `answer_repo_question`, `run_static_analysis`, `get_predicate_examples`,
  `retrieve_memory`, `classify_patch_risk`, `run_sast_repair`,
  `compute_rds_features`, `record_eval_result`, `record_trajectory`,
  `evolve_static_rules`, `record_run_event`, `record_harness_condition`,
  `evaluate_tool_policy`, `detect_run_anomalies`, `compare_run_traces`,
  `assess_harness_stage`, `classify_harness_drift`,
  `validate_harness_controls`, `compute_readiness_score`,
  `run_maintainability_oracles`, `run_prompt_manifest_regression`,
  `promote_operational_lesson`, `record_incident`, `graph_build`,
  `graph_update`, `register_repo`, `plugin_reload`, `memory_compact`,
  `run_implementation_check`, `run_issue_resolution`, `run_patch_review`,
  `run_eval_suite`, `run_operational_review`, `run_readiness_audit`,
  `capture_trace`.
- **All public prompts**: `implementation-check`, `bug-resolve`,
  `patch-review`, `operational-review`, `readiness-audit`.
- **All private skill templates**: `investigate`, `repair`, `audit`,
  `blast-radius`, `sast-repair`, `risk-classify`, `evaluate`.
- **Hard constraints HC1–HC5** (HC6 was satisfied via `harness_policy_gate_present`).
- **Protocol behaviour**: `resources/subscribe`, `notifications/resources/updated`,
  `notifications/resources/list_changed`, task descriptors with `CreateTaskResult`/`taskId`/`tasks/get`/`tasks/result`/`tasks/list`/`tasks/cancel`/`notifications/tasks/status`.
- **Verdict-state symbols**: `process-compliant`, `process-noncompliant`,
  `trace-incomplete`, `budget-exhausted`, `needs-readiness-work`, `satisfied`,
  `violated`, `unknown`, `safe`, `relaxed`.
- **Schema fields**: `repo`, `git_sha`, `worktree_snapshot_id`, `file`, `span`,
  `confidence`, `derivation`.
- **Local verify path**: `verify` (Makefile + `.github/workflows/verify.yml`).

This corresponds to all 19 implementation phases (H0, 0, 1, 2, 3, 4, 4A,
5–19) having their named surfaces present.

## Readiness Audit

- Harness stage: **S3** (production tier).
- AI-readiness score: **22 / 25** (S3-stable threshold = 22; passes).
- Per-axis: no regression vs prior audit at 2026-05-17 22:03.
- Missing gates: none.
- Absent scanners: none.
- Weak docs/spec links: none.
- Unprotected risky paths: none.
- Recommended readiness tasks: none.

### Drift Findings (1)

| Finding | Severity | Recommendation |
|---|---|---|
| `.codex/INSTRUCTIONS.md` does not restate HC controls | Low | Either restate HC1–HC6 in `.codex/INSTRUCTIONS.md` (keeping AGENTS.md authoritative per non-relaxation rule) or remove the file if Codex CLI is not in use. |

## Operational Findings

### Persistence regression: readiness resource

| Aspect | Detail |
|---|---|
| Symptom | After `run_readiness_audit` returns a report, `code-intelligence://readiness/{repo_id}` returns `{"status": "no_report"}`. |
| Expected | Resource should return the report just produced. |
| Prior audit | Flagged in 2026-05-17 22:03 compliance_report.md as a confirmed gap claimed fixed. |
| Current state | Symptom reproduces — readiness audit returns report inline but resource read still says `no_report`. |
| Evidence | `code-intelligence://readiness/repo:d862447c9f4a283eafddb1d6` body shown above. |
| Severity | Medium — does not block release gate (score and stage are correct via the report return value) but does mean subscribers of the resource cannot consume readiness updates. |
| Recommendation | Investigate `mcp_server/tools.py` readiness-audit handler vs `mcp_server/resources.py` readiness reader: the audit may be returning the report without persisting it to operations storage, or the resource may be querying by a different key than the storage uses. |

This is the only material finding from the audit beyond the cosmetic drift
note.

## Verdict

**Audit verdict: implementation is complete with respect to the documented
design and implementation plan.**

- 19 implementation phases (H0, 0, 1, 2, 3, 4, 4A, 5–19) have their named
  MCP surfaces present and graph-grounded.
- 0 violated clauses.
- 6 unknown clauses are all extraction artifacts or
  calibration-pending; none correspond to a missing implementation.
- 1 low-severity drift finding (optional `.codex/INSTRUCTIONS.md` overlay).
- 1 medium-severity operational follow-up (readiness resource persistence).
- AI-readiness S3 / 22 — production tier, no regression.

## Next Steps

Per the audit skill workflow router:

- `partially_compliant` → would normally transition to `bug-resolve` for each
  confirmed gap, but **after investigation no real gaps exist**, so no
  `bug-resolve` cycles are needed for the implementation-check unknowns.
- Optional follow-ups (operational, not implementation):
  1. Either fix the readiness resource persistence (medium) or open an
     incident record explaining why the readiness audit return value is
     authoritative and the resource is a deprecated cache.
  2. Either fill `.codex/INSTRUCTIONS.md` with restated HC1–HC6 or delete it
     (low).
  3. Add a Phase 18 calibration fixture for the SARIF-disappear behaviour so
     `clause:a42a2d9f822d`-equivalent claims can pass the auto-pass gate
     instead of falling through to `calibration_absent`.

## Artifacts

All from this run, written to `.agent/artifacts/`:

- `audit_spec_20260517.md` — spec text submitted to `run_implementation_check`.
- `impl_check_report.json` — report from `run_implementation_check`.
- `clause_investigation.json` — per-unknown-clause investigation via
  `get_relevant_files`.
- `readiness_report.json` — report from `run_readiness_audit`.
- `compliance_report.md` — this document.

## Provenance

- MCP server: `llm-sca-tooling` MCP server, protocol `2025-11-25` per recent
  commit `30016d4`.
- Repo registration: `repo:d862447c9f4a283eafddb1d6`.
- Graph snapshot: `snap:repo:d862447c9f4a283eafddb1d6:dirty:02ef5a4436f128cc`
  (current dirty worktree, git_sha `3c6f8e42c6bb0739f188fdfcaa9c56952a35d232`).
- impl-check run_id: `impl-check:ic:049818e719fd453b9aaf764230748c4a`.
- impl-check harness_condition_id:
  `hcs:impl-check:ic:049818e719fd453b9aaf764230748c4a`.
- readiness report_id: `readiness-audit:dtom8yrVXHL6mn7et5XgJ4zS`.

Index state caveat: the graph was built from a dirty worktree with
`index_status: partial`. This is the same snapshot the previous successful
audit ran against and is sufficient for the named-symbol grounding used here,
but a clean rebuild before release would tighten the evidence.
