# Operational Review — research-pipeline v0.17.8

**Date**: 2026-05-12
**Run ID**: `release:research-pipeline:v0.17.8`
**HCS**: `.agent/eval/hcs-release-v0.17.8.md`

---

## Confirmed Findings

*(All citations reference artifacts in `.agent/artifacts/` or `.agent/eval/`.)*

1. **Architecture compliance: functionally complete**
   - Source: `compliance_report.md` → "Confirmed Implementations" section
   - 0 violated clauses, 56/57 unknown clauses confirmed implemented via direct inspection
   - All 7 core pipeline stages, 5 auxiliary commands, 11+ MCP tools verified

2. **GAP-001 resolved** (naming drift, low severity)
   - Source: `compliance_report.md` → "Confirmed Gaps / GAP-001"
   - `docs/architecture.md:277` corrected `ARXIV_PAPER_PIPELINE_CONFIG` → `RESEARCH_PIPELINE_CONFIG`
   - Patch risk: `safe` (`patch_risk.json`, diff:69fa6bf49bcd505b)

3. **T1 gate: all checks pass**
   - Source: `hcs-release-v0.17.8.md` → "Gate Results / T1"
   - 4331 unit tests pass; ruff, mypy, bandit, pip-audit all exit 0

4. **CI passing on master**
   - Source: `hcs-release-v0.17.8.md` → "CI Gate"
   - GitHub Actions run 25735103794: Lint, Test 3.12, Test 3.13, Type Check, Security all ✅

5. **Readiness no-regression**
   - Source: `readiness_report.json` (run `readiness-audit:XIcxtg2XkXvkC13QiKl41h_-`)
   - S3 harness stage, score 22, zero drift findings, zero blockers

---

## Assumptions and Uncertainties

- **Partial graph build**: The MCP graph index covered 7 nodes vs ~300+ files (`compliance_report.md`
  Note). Direct source inspection compensated for this, but a full re-index would provide stronger
  formal guarantees. Confidence impact: low (56/57 clauses independently verified).

- **T2 gate (harness tests)**: `tests/harness/` does not exist in research-pipeline, so harness
  regression tests were not run. No harness tests were skipped or degraded.

- **LLM provider module** (`src/research_pipeline/llm/`): marked "experimental" in spec;
  confidence 0.80 on completeness per `clause_investigation.json`.

---

## Release Risk Assessment

**Overall risk: LOW**

The change set is minimal — one documentation line corrected, one workflow action version pinned,
version bump. No code logic changed. All deterministic gates pass.

---

## Recommended Follow-Up

1. Re-run `graph_build` with full indexing after release to resolve the 57 MCP-unknown clauses
   formally (no blocking concern for this release).
2. Add `tests/harness/` suite to research-pipeline for T2 gate coverage in future releases.
3. Monitor `astral-sh/setup-uv@v8` tag availability; upgrade when published to marketplace.
