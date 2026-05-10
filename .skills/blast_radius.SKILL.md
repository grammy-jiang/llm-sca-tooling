---
name: blast-radius
description: >
  Phase 15 hardened blast-radius skill — change-type-specific traversal,
  eight impact groups, cross-language and cross-repository analysis,
  C/C++ ABI impact, generated-stub reporting, ambiguous-link separation,
  and a human-readable impact report with evidence citations.
metadata:
  version: 0.2.0
  phase: "15"
  replaces: "Phase 13 BlastRadiusStub"
---

# blast-radius

Private skill template for the blast-radius stage of the bug-resolve workflow.
Graduated from Phase 13 stub to full Phase 15 service.

## Entry

`blast-radius(change_set, repos?)`

## Instructions

1. Call `BlastRadiusService.compute(diff_id, changed_symbol_records)`.
2. Read the `BlastRadiusReport`.
3. Report all **eight** impact groups with counts and representative examples:
   - `direct_callers` — nodes with `calls` edge to changed symbols (hop 1).
   - `downstream_behaviours` — callers-of-callers via `calls` / `dataflow` (hop 2+).
   - `tests` — test nodes reachable via `tests` edge.
   - `interfaces` — nodes at `exposes` / `consumes` / `ffi` / `implements` boundaries.
   - `services` — nodes beyond a service boundary (cross-language or cross-process).
   - `repositories` — nodes in other registered repos reachable via cross-repo overlay.
   - `sarif_reachability` — static-analysis rules activated by the changed code path.
   - `linked_docs_specs` — design clauses / intent nodes with `satisfies`/`documents` edges.
4. Report `generated_stub_notes` with recommended actions.
   - Flag `manual_edit_policy_flag=true` as a policy violation unless allowlisted.
5. Report `abi_impact_notes` for C/C++ changes.
   - When backend is absent, report `abi_change_type=unknown` with diagnostic — never skip.
6. Report `cross_repo_impact_records` with consuming repos and node counts.
7. **Never merge ambiguous links with confirmed links.**
   - `impact_groups` contains only confirmed records (confidence ≥ analyser threshold).
   - `ambiguous_links` contains candidate-level and low-confidence links separately.
8. State `is_partial: true` with the `partial_reason` when:
   - Cross-repo overlay unavailable or incomplete.
   - C/C++ backend not available for ABI analysis.
   - Any registered repo has a stale index.
9. Flag `sarif_reachability_summary` changes (increased or decreased risk).
10. Flag stale implementation-check verdicts in `linked_docs_summary`.

## Change-Type Traversal Policies

| Change type              | Max hops | Cross-language | Cross-repo | SARIF |
|--------------------------|----------|---------------|------------|-------|
| INTERNAL_IMPLEMENTATION  | 3        | No            | No         | No    |
| PUBLIC_API_CHANGE        | 5        | Yes           | Yes        | No    |
| IDL_SCHEMA_CONTRACT_CHANGE | 6      | Yes           | Yes        | Yes   |
| SECURITY_SENSITIVE_CHANGE | 4       | Yes           | Yes        | Yes   |
| GENERATED_FILE_CHANGE    | 2        | No            | No         | No    |
| MIXED                    | max(applicable) | max | max     | Yes   |

## Rules

- `confirmed_links` must be graph-verified (edge confidence ≥ analyser threshold).
- Speculative and candidate-level links always go in `ambiguous_links`.
- `is_partial` must be set when cross-repo or ABI analysis is unavailable.
- Generated-file manual edits must be flagged unconditionally (unless allowlisted).
- ABI analysis produces `abi_change_type=unknown` when clangd absent — never silently skip.
- Ambiguous links must never be merged into `impact_groups`.
- Template snapshot must be stable across equivalent inputs.
