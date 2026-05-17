# Docs Audit Findings Fix Plan

Date: 2026-05-17

## Scope

This document defines the remediation plan for the findings from the MCP-backed
docs audit. It does not cover the separate operational issue where `make verify`
appeared stalled during quiet scanner phases.

## Audit Summary

The docs audit produced a `partially_compliant` verdict:

- Satisfied clauses: 5
- Violated clauses: 0
- Unknown clauses: 5
- Recommendation: `review-required`
- Readiness stage: S3
- AI-readiness score: 22
- Missing gates: none
- Weak docs/spec links: none
- Readiness drift finding: `.codex/INSTRUCTIONS.md does not restate HC controls`

Primary audit artifacts:

- `.agent/artifacts/docs_audit_impl_check_20260517.json`
- `.agent/artifacts/docs_audit_clause_investigation_20260517.json`
- `.agent/artifacts/docs_audit_readiness_20260517.json`
- `.agent/artifacts/docs_audit_compliance_report_20260517.md`

## Findings

### Finding 1 - Runtime overlay drift in `.codex/INSTRUCTIONS.md`

The readiness audit reports:

```text
.codex/INSTRUCTIONS.md does not restate HC controls
```

Risk:

- Runtime overlays can become ambiguous even if they do not explicitly relax
  `AGENTS.md`.
- Agents using the Codex overlay may not see the same HC1-HC6 controls unless
  they also read `AGENTS.md`.
- This weakens the non-relaxation model because drift detection has a concrete
  finding against one overlay.

Fix plan:

1. Update `.codex/INSTRUCTIONS.md` to restate or explicitly import the HC1-HC6
   controls from `AGENTS.md`.
2. Ensure the overlay says it may specialize execution details but must not
   relax hard constraints or quality gates.
3. Keep the wording short and mechanical so future drift checks can match it.
4. Run manifest regression tests and readiness audit after the update.

Acceptance criteria:

- `run_readiness_audit` reports no drift finding for `.codex/INSTRUCTIONS.md`.
- `tests/harness/test_non_relaxation.py` and
  `tests/harness/test_manifest_regression.py` pass.
- `make verify` passes.

### Finding 2 - Five implementation-check clauses remained unknown

The implementation check found no violated clauses, but it could not prove five
clauses. The unknowns are review-required until the audit can cite exact
evidence.

Risk:

- A `partially_compliant` verdict cannot be treated as full docs acceptance.
- Future agents may need to manually reason about governance coverage instead
  of relying on deterministic evidence.
- The repository cannot distinguish "missing documentation" from "documentation
  exists but the index cannot see it".

Fix plan:

1. Map each unknown clause to the intended source of truth.
2. For each clause, identify whether the evidence should live in `AGENTS.md`,
   a runtime overlay, `.agent/docs/`, `.agent/templates/`, `.agents/skills/`,
   `schemas/`, or public `docs/`.
3. Add a small audit trace table in a public docs file that points each clause
   to its canonical source.
4. Rerun `run_implementation_check` and compare unknown-clause count.

Acceptance criteria:

- Unknown clauses drop from 5 to 0, or each remaining unknown has an approved
  waiver explaining why it cannot be proven by the current MCP index.
- The implementation-check verdict becomes `compliant`, or the only remaining
  status is a documented tool limitation.

### Finding 3 - Hidden governance paths were skipped by the graph build

The graph build diagnostics showed skipped governance-bearing paths:

- `.agent`
- `.agents`
- `.codex`
- `.github`

Risk:

- Important contracts, templates, runtime overlays, and skill definitions are
  invisible to the implementation-check evidence pipeline.
- Audit results can incorrectly return `unknown` even when documentation exists.
- Reviewers lose file-level confidence for the most important governance
  artifacts.

Fix plan:

1. Decide which hidden paths should be indexable for governance audits.
2. Add a safe allowlist for read-only graph indexing of selected hidden paths:
   `.agent/docs/`, `.agent/templates/`, `.agents/skills/`, `.codex/`, and
   `.github/workflows/`.
3. Keep secret-bearing paths excluded:
   `.env`, `.env.*`, `*.key`, `*.pem`, `credentials/`, and `secrets/`.
4. Add regression coverage that proves allowed hidden governance paths are
   indexed and excluded secret paths remain skipped.
5. Rerun graph build and implementation check.

Acceptance criteria:

- Graph build diagnostics no longer skip the selected governance paths.
- Secret and credential paths remain excluded.
- Implementation-check evidence can reference hidden governance artifacts where
  appropriate.

### Finding 4 - Markdown evidence lacked exact line spans

The clause investigation found related Markdown and schema files, but MCP
responses returned `span=null` and no exact file:line evidence for Markdown
docs.

Risk:

- Final audit reports cannot cite exact lines for documentation clauses.
- Human review has to reopen files manually, which weakens reproducibility.
- Clause-level confidence remains lower than necessary.

Fix plan:

1. Extend Markdown indexing to produce heading, paragraph, table-row, and list
   item spans.
2. Include stable `file_path:start_line` evidence in `get_relevant_files`
   responses for Markdown files.
3. Add tests using representative docs with headings, tables, and bullet lists.
4. Re-run clause investigation for the five unknown docs clauses.

Acceptance criteria:

- `get_relevant_files` returns exact spans for Markdown evidence.
- Clause investigation can cite file:line for every docs finding.
- No direct shell/manual grep is needed for docs evidence.

### Finding 5 - Run-record confirmation had incomplete harness-condition linkage

The implementation-check artifact confirmed a trace harness condition id, but
the run-record resource had `harness_condition_id: null`.

Risk:

- Evidence consumers may see different harness-condition state depending on
  whether they read the run record or the trace manifest.
- A run can look less complete than it actually is.

Fix plan:

1. Update the implementation-check run-record writer so the run record stores
   the same harness condition id as the trace manifest.
2. Add a regression test that reads `code-intelligence://runs/{run_id}` and
   verifies the harness condition id is populated for implementation checks.
3. Re-run a docs implementation check and confirm both resources agree.

Acceptance criteria:

- `code-intelligence://runs/{run_id}` contains a non-null
  `harness_condition_id`.
- `trace://{run_id}` and the run record report the same harness condition id.

## Recommended Implementation Order

1. Fix `.codex/INSTRUCTIONS.md` drift first because it is the only readiness
   blocker explicitly reported by MCP.
2. Add hidden governance path indexing so audit tools can inspect the contracts
   they are expected to enforce.
3. Add Markdown span evidence so docs findings can cite exact lines.
4. Build the unknown-clause trace table and rerun implementation check.
5. Fix run-record harness-condition linkage.
6. Run the full gate set:
   - `make verify`
   - `local-agent-harness check --repo .`
   - MCP `run_implementation_check`
   - MCP `run_readiness_audit`

## Final Acceptance Criteria

The docs audit findings are resolved when:

- Readiness audit reports no `.codex/INSTRUCTIONS.md` drift.
- Implementation check reports 0 violated clauses and 0 unknown clauses, or a
  reviewed waiver exists for any remaining unknown.
- Graph build indexes the approved hidden governance paths and still excludes
  secret-bearing paths.
- Markdown evidence includes exact file:line spans.
- Run records and trace manifests agree on harness condition ids.
- `make verify` exits 0 after all changes.
