# Benchmark Wiring Plan — Closing the Phase 18 Loop

**Author**: grammy.jiang (with audit assistance)
**Date**: 2026-05-18 (revision 3 — Track A landed in v0.5.0, Track B audit completed inline)
**Status**:
- Track A — **implemented in v0.5.0** (2026-05-18). `run_release_gate()` wired,
  CLI switched, `make release-gate` target added, e2e tests pinning the
  contract.
- Track B — **audit completed inline in this chat** (see § Track B below).
  All Phase 18 §4 minimums were verified met against the existing fixture
  lists; no backfill needed at v0.5.0.
- Track C — **deferred** until a real-LLM backend lands; Phase 18 §9
  production-derived refresh has no value until releases are exercising
  the gate in production.

---

## 0. What changed in this revision

The first draft of this plan was scoped around *downloading external
benchmarks* (SWE-bench Lite, HumanEval, etc.). That framing turned out
to be a misread:

1. The design docs explicitly **don't** want external datasets in the
   gate (Phase 10 §3 non-goals, Phase 18 §4 "-style fixtures").
2. The user's own request was based on the mistaken assumption that
   filling fixtures requires external data — it doesn't.
3. The actual gap is much narrower and more tractable: **the
   already-existing fixtures, runners, calibration math, and release
   gate are not yet wired together end-to-end.**

This revision discards the external-download track entirely and refocuses
on closing the internal loop. The result is a smaller, governance-clean,
shippable plan.

---

## 1. The real gap (root cause)

### 1.1 What exists today (v0.4.4)

| Component | Path | State |
|---|---|---|
| T1 fixtures (5 instances) | `tests/evaluation/fixtures/smoke/` | ✅ Present |
| T3 fixtures (5 instances) | `src/llm_sca_tooling/evaluation/t3_runner.py` `default_t3_fixtures()` | ✅ Present |
| T4 fixtures (5 instances) | `src/llm_sca_tooling/evaluation/t4_runner.py` `default_t4_fixtures()` | ✅ Present |
| T1 runner | `evaluation/t1_runner.py` | ✅ Real implementation |
| T2 runner | `evaluation/t2_runner.py` | ✅ Skeleton |
| T3 runner `run_t3_null` | `evaluation/t3_runner.py` | ✅ Real implementation |
| T4 runner `run_t4_null` | `evaluation/t4_runner.py` | ✅ Real implementation |
| Calibration math | `release/calibration.py` | ✅ Real ECE computation |
| Calibration thresholds | `release/calibration.py:16–18` | ✅ `0.10` for patch / impl |
| Operational gates | `release/operational_gates.py` | ✅ Real implementation |
| Adversarial check suite | `release/adversarial.py` | ✅ Real fixture-based suite |
| Production refresh model | `release/production_refresh.py` | ✅ Model + scaffolding |
| `ReleaseGateEvaluator` | `release/release_gate.py:30–124` | ✅ Real evaluator |
| CLI `release-gate` command | `cli/main.py:99`, `cli/release.py:23` | ⚠️ Calls fixture-builder, not real runners |
| CHANGELOG benchmark numbers | `CHANGELOG.md` | ❌ Absent for v0.4.x |
| `make verify` includes release-gate | `Makefile:21` | ❌ verify does not invoke release-gate |
| Production-derived refresh loop | n/a | ❌ Model exists, capture flow not wired |

### 1.2 The actual missing wire

`release/release_gate.py` exports two distinct entry points:

| Entry point | What it does today | What the design wants |
|---|---|---|
| `ReleaseGateEvaluator.evaluate(...)` | Given benchmark results, a calibration report, operational gate result, and adversarial results, evaluates pass/fail and returns a `ReleaseGateResult` | Same — already correct |
| `build_passing_fixture_release_gate(...)` | **Fabricates** passing inputs and feeds them to the evaluator, so the evaluator itself is testable | A *real* `run_release_gate(...)` that actually executes T1–T4 against the in-repo fixtures, computes ECE from real outputs, and feeds the evaluator |

The CLI commands `release-gate` (in both `cli/main.py` and `cli/release.py`)
invoke `build_passing_fixture_release_gate`. There is **no function** in
the codebase today that runs the actual benchmarks and feeds real
results into the gate.

### 1.3 Symptom in the v0.4.4 release

The v0.4.4 CHANGELOG entry lists code changes only. No benchmark numbers
appear. No `ReleaseGateResult` was produced. No CalibrationReport was
stamped. The release was approved on a passing `make verify` and a
docs-audit, with the release gate's actual purpose — *measurement of
the tool's predictive quality* — sidestepped entirely.

This is the gap the user is pointing at.

---

## 2. What "make it work" means in concrete terms

A successful end state is reached when **every minor or major release**
of evidence-sca:

1. Runs T1, T3, and T4 against their in-repo fixtures.
2. Produces a real `CalibrationReport` with ECE numbers computed from
   the runners' actual outputs.
3. Produces a real `ReleaseGateResult` that captures pass/fail per gate
   (calibration, operational, adversarial, memory ship, AI-readiness).
4. **Blocks the release** if any required gate fails.
5. **Stamps the numbers** in `CHANGELOG.md` per the entry for that
   version, alongside the existing "Added / Fixed" sections.
6. Persists the `ReleaseGateResult` as an audit artifact under
   `.agent/eval/runs/<release-tag>/`.

That is what Phase 18 specifies, and the only thing missing is the
glue code that connects components that already exist.

---

## 3. Three tracks, in priority order

### Track A — Wire the actual release gate (1–2 days, no governance change)

This is the load-bearing track. It closes the loop.

#### A.1 Add a real release-gate runner

Add a new function `run_release_gate` (or `build_release_gate`) in
`src/llm_sca_tooling/release/release_gate.py`:

```python
def run_release_gate(
    *,
    suite: str = "all",
    calibration_required: bool = True,
    adversarial_required: bool = True,
    memory_gate_required: bool = True,
    operational_gate_required: bool = True,
    fail_on_any: bool = True,
    fixtures_dir: Path | None = None,
) -> ReleaseGateResult:
    """Run the real Phase 18 release gate against in-repo fixtures.

    Replaces ``build_passing_fixture_release_gate`` for production use.
    The fixture-builder remains for unit-testing the evaluator only.
    """
    # 1. Execute the runners.
    t1_result = run_t1_smoke(fixture_dir=fixtures_dir or _default_smoke_dir())
    t3_result = run_t3_null(fixtures=default_t3_fixtures())
    t4_result = run_t4_null(fixtures=default_t4_fixtures())

    # 2. Convert per-instance results to CalibrationSamples.
    patch_samples = _patch_samples_from_t3(t3_result)
    impl_samples = _impl_samples_from_t4(t4_result)

    # 3. Build the calibration report from real samples.
    calibration = build_calibration_report(
        eval_run_id=f"release-gate:{_now_iso()}",
        model_backend="null",  # the null backend is the canonical pre-LLM baseline
        harness_condition_id=...,
        patch_risk_samples=patch_samples,
        impl_check_samples=impl_samples,
        repo_qa_file_loc_accuracy=...,   # from a real or stubbed repo-QA pass
        repo_qa_behaviour_tracing_accuracy=...,
        memory_her_eviction_delta_pp=...,
        rds_v2_summary=_rds_summary(t3_result, t4_result),
    )

    # 4. Operational gates from real run records (use the eval runs).
    operational = compute_operational_harness_gate(
        eval_run_id=..., run_records=_records_from_runs(t1_result, t3_result, t4_result),
        readiness_threshold_met=True,
    )

    # 5. Adversarial suite (fixture-based, already real).
    adversarial = run_adversarial_suite()

    # 6. Compose benchmark results.
    benchmark_results = [
        BenchmarkSuiteResult.from_t1(t1_result),
        BenchmarkSuiteResult.from_t3(t3_result),
        BenchmarkSuiteResult.from_t4(t4_result),
    ]

    # 7. Evaluate.
    return ReleaseGateEvaluator().evaluate(
        harness_condition_id=...,
        benchmark_results=benchmark_results,
        calibration_report=calibration,
        operational_gate_result=operational,
        adversarial_check_results=adversarial,
        memory_ship_gate_result_ref=...,
        ai_readiness_report_ref=...,
        calibration_required=calibration_required,
        adversarial_required=adversarial_required,
        memory_gate_required=memory_gate_required,
        operational_gate_required=operational_gate_required,
        fail_on_any=fail_on_any,
    )
```

Effort: ~half day for the function, ~half day for the adapter functions
(`_patch_samples_from_t3`, `BenchmarkSuiteResult.from_t1`, …).

#### A.2 Switch the CLI from fixture to real

Replace the call sites in `cli/main.py:130–145` and `cli/release.py:41–60`:

```python
# before
result = build_passing_fixture_release_gate(...)

# after
result = run_release_gate(...)
```

Keep `build_passing_fixture_release_gate` for use in `tests/release/`.

Effort: ~half hour. Two-line change plus test fixture path updates.

#### A.3 Wire into the release procedure

Two options:

| Option | Pros | Cons |
|---|---|---|
| **A.3.a — Make `make verify` include release-gate** | Simple; one entry point | Slows every commit; T3/T4 runs add seconds; eventually minutes when fixtures grow |
| **A.3.b — Add `make release-gate` as a separate target invoked by the `ship` skill / release procedure** | Decouples commit-time gate from release-time gate; matches phase 18 §2 — release gate is per-release, not per-commit | Two gates to remember |

**Recommendation: A.3.b.** Add `make release-gate` and document in the
`ship` skill that `make release-gate` must exit 0 before `git tag`.

Effort: ~1 hour for Makefile target + ship skill update.

#### A.4 Stamp numbers in CHANGELOG

For the next minor release (v0.5.0), the changelog entry must include
a `### Release-gate metrics` subsection populated by reading
`.agent/eval/runs/<tag>/release_gate_report.json`. A simple
`scripts/render_changelog_metrics.py` can extract and format the
top-line numbers.

Effort: ~1 hour for the script + docs.

#### A.5 Tests

Add new tests in `tests/release/test_release_gate_e2e.py`:

- `test_run_release_gate_against_fixtures_produces_passing_result` — golden test that the real gate passes against the in-repo fixtures.
- `test_run_release_gate_detects_calibration_regression` — temporarily perturb a fixture to produce a known ECE > 0.10; assert the gate fails.
- `test_release_gate_report_is_persisted_under_eval_runs` — assert the artefact lands under `.agent/eval/runs/...`.

Effort: ~half day.

#### A.6 Track A total

- Code: ~1.5 days
- Tests: ~0.5 day
- Docs: ~0.5 day
- Governance: zero — all changes inside the write allowlist

**End-of-track outcome**: v0.5.0 ships with a real CalibrationReport in
its changelog, the release-gate command runs the actual runners, and the
ship procedure refuses to tag a version whose gate fails.

---

### Track B — Strengthen the in-repo fixtures (audit completed inline 2026-05-18)

**Audit status as of 2026-05-18 (v0.5.0 release)**: all Phase 18 §4
minimums are already met. The audit was performed inline against the
fixture lists in `t3_runner.default_t3_fixtures()` and
`t4_runner.default_t4_fixtures()`:

T3 (Phase 18 §4.1):

| Requirement | Status | Evidence |
|---|---|---|
| ≥3 SWE-PolyBench-style (Python + TypeScript) | ✅ 3 | `swe-polybench-python-typescript-route`, `swe-polybench-python-typescript-websocket`, `swe-polybench-generated-client` |
| ≥2 Defects4C-style (C/C++) | ✅ 2 | `defects4c-cpp-header-abi`, `defects4c-cpp-test-entry` |
| ≥1 `GeneratedStubImpactNote` instance | ✅ 1 | `swe-polybench-generated-client` (`generated_file_impact=True`) |

T4 (Phase 18 §4.2):

| Requirement | Status | Evidence |
|---|---|---|
| ≥3 CodeSpecBench-style | ✅ 3 | `codespecbench-authz`, `codespecbench-cache`, `codespecbench-policy` |
| ≥2 Vul4J-style | ✅ 2 | `vul4j-path-traversal`, `vul4j-deserialisation` |
| ≥1 `violated` clause | ✅ 3 | `codespecbench-authz`, `vul4j-path-traversal`, `vul4j-deserialisation` |
| ≥1 `unknown` clause | ✅ 2 | `codespecbench-cache`, `vul4j-deserialisation` |
| Per-clause ECE bucket populated | ✅ | `clause_family` field set on every fixture |

**No backfill required for v0.5.0.**

Two refinements observed during the audit but deferred (low priority):

1. All fixtures have `predicted == gold` and `probabilities = [0.95, …]`.
   The null backend trivially passes, which validates wiring rather than
   accuracy. Real LLM backends will exercise the gate; the existing
   adversarial suite (`release/adversarial.py`) covers intentional
   failure cases.
2. ECE buckets are clustered at 0.9–1.0. Calibration coverage broadens
   when real-LLM backends produce predictions across the confidence
   spectrum — not something a null backend can manufacture.

Either deferred item could become work if a future release wants to
strengthen `release/adversarial.py` coverage, but neither is a
prerequisite for shipping v0.5.0.

---

### Track B (original scope — pre-audit) — Strengthen the in-repo fixtures (1 day, optional, no governance change)

After Track A is wired, the **numbers it produces are only as
meaningful as the fixtures they run against**. A gate that always
passes because the fixtures are too tame is no better than the
fixture-builder it replaced.

Phase 18 §4 sets a minimum bar:

| Suite | Phase 18 §4 requires | Today |
|---|---|---|
| T3 | ≥3 SWE-PolyBench-style + ≥2 Defects4C-style, ≥1 exercising `GeneratedStubImpactNote` | 5 instances; need to verify `GeneratedStubImpactNote` coverage |
| T4 | ≥3 CodeSpecBench-style + ≥2 Vul4J-style, **≥1 `violated`** + **≥1 `unknown`** | 5 instances; need to verify violated/unknown coverage |
| Calibration | Per-clause ECE bucket populated for every instance | Need to verify field is set per fixture |

#### B.1 Audit

A one-page audit document under `.agent/docs/fixture-audit-2026-05-18.md`
records: for each fixture in `default_t3_fixtures()` and
`default_t4_fixtures()`, which Phase 18 §4 requirement it satisfies and
which it does not.

Effort: ~half day.

#### B.2 Backfill

Where the audit finds gaps, add the missing fixtures **as new entries
in `default_t3_fixtures()` / `default_t4_fixtures()`**. The fixtures
remain hand-authored "-style" instances per design intent — no
external data.

Likely backfills (to be confirmed by audit):

- T3: one fixture explicitly tagged `generated_file_impact=True` may already exist; if not, add one.
- T4: one fixture with `predicted="unknown"` (e.g., a behavioural clause whose evidence is calibration-pending) — likely already covered by `codespecbench-authz` or similar; verify.
- T4: one fixture with `predicted="violated"` (e.g., a deliberately incorrect implementation against a spec clause) — likely needs to be added.

Effort: ~half day if 1–2 fixtures need adding.

#### B.3 Track B total

- Code: ~half day
- Tests: trivial — fixtures auto-tested by the runners
- Docs: ~half day audit doc
- Governance: zero

---

### Track C — Wire Phase 18 §9 production-derived refresh (3–5 days, after Track A and B, no governance change)

This is the design's preferred long-term mechanism for growing the
corpus over time. The `ProductionEvalRefreshRecord` model and
`production_refresh.py` already exist; what is missing is the **capture
flow**.

#### C.1 The capture loop

Phase 18 §9.2 describes the flow:

1. When `run_issue_resolution` or `run_implementation_check` produces a
   result, the run record is eligible for refresh consideration.
2. A filter (configurable per HC6, redacting issue text and removing
   solution diffs) determines if the run is suitable.
3. Suitable runs become `ProductionEvalRefreshRecord` entries with
   `gold_patch_hidden=True` and `approved=False` until human review.
4. Approved entries are added to the relevant suite (`added_to_suite_id`)
   and become available to T1–T4 runners on subsequent gate runs.

#### C.2 Implementation outline

```text
src/llm_sca_tooling/evaluation/
  production_refresh_capture.py    # filters and stages PER candidates
  production_refresh_approver.py   # CLI for human review and approval

src/llm_sca_tooling/cli/
  refresh.py                       # llm-sca-tooling refresh review/approve

tests/evaluation/
  test_production_refresh_capture.py
  test_production_refresh_approver.py
```

Each new fixture goes into a versioned, gitignored corpus under
`.agent/eval/corpora/<suite>/` and is referenced by `instance_id` from
the existing default fixture lists. This keeps the in-repo commits clean
while letting the gate use production-derived data.

#### C.3 Effort and gating

- Code: ~2 days for capture + approver
- Tests: ~1 day (the filter contract is the load-bearing piece)
- Docs: ~half day operator runbook
- Governance: zero — all activity inside the existing write allowlist

**End-of-track outcome**: the next time someone runs `bug-resolve` or
`implementation-check` against a real repo with evidence-sca, the result
becomes a candidate for inclusion in the benchmark corpus, with HC6
redaction enforced at capture time and human approval required before
the instance counts toward the release gate.

---

## 4. Recommended sequencing

```text
v0.4.4 (today)
    │
    ▼
Track A: wire release-gate to real runners            ──► v0.5.0
    • run_release_gate() in release/release_gate.py
    • CLI switches from fixture-builder to real runner
    • make release-gate target
    • numbers stamped in CHANGELOG.md
    │
    ▼
Track B: fixture audit + backfill (optional but useful)  ──► v0.5.0 or v0.5.1
    • verify Phase 18 §4 minimums met
    • add the violated/unknown T4 fixture if missing
    │
    ▼
Track C: production-derived refresh                  ──► v0.6.0 / v1.0
    • capture loop wired
    • approver CLI
    • first instances added from real usage
```

Each track is independently shippable. Track A is the *necessary
work* — it converts "release gate exists in code" to "release gate
governs actual releases". Track B and C build on Track A.

---

## 5. What this plan explicitly does NOT do

| Excluded scope | Why |
|---|---|
| Download SWE-bench / Defects4J / HumanEval | Phase 10 §3 non-goal; design uses "-style" fixtures |
| Change HC5 network egress allowlist | Not needed — the gate runs offline |
| Add `huggingface.co` or any HF dependency | Same as above |
| Touch the architecture or implementation plan docs | Wiring change only; design unchanged |
| Modify the AGENTS.md write allowlist | All new code lives in already-allowed paths |
| Rewrite any existing runner / fixture / model | Wiring connects existing pieces |

This is a pure integration-completion plan: no new design surface,
no new external dependencies, no governance amendments.

---

## 6. Decision points for the human owner

1. **Approve Track A?** Recommend yes — this is the load-bearing fix.
   The release gate is a documented Phase 18 deliverable and is the
   only correct way to claim a v0.5.0 release is production-grade.

2. **Approve Track B?** Recommend yes for the audit (half-day, no
   risk), backfill only if the audit finds real gaps.

3. **Approve Track C now or defer?** Recommend defer until Track A and
   B land. The capture loop has value only once releases are running
   the real gate.

4. **Where do release-gate report artefacts live?** Recommend
   `.agent/eval/runs/<tag>/release_gate_report.json` (gitignored, lives
   in the audit trail like other run records).

5. **`make verify` or `make release-gate` split (A.3)?** Plan
   recommends the split — keeps commit-time gate fast, runs the full
   gate only at release time.

---

## 7. Concrete first action (if Track A is approved)

```bash
# 1. Inspect what each runner returns
uv run python -c "
from llm_sca_tooling.evaluation.t3_runner import run_t3_null, default_t3_fixtures
result = run_t3_null(fixtures=default_t3_fixtures())
print(result.model_dump_json(indent=2)[:500])
"

# 2. Inspect the CalibrationSample / BenchmarkSuiteResult shapes
uv run python -c "
from llm_sca_tooling.release.models import (
    BenchmarkSuiteResult, CalibrationReport
)
import json
print(json.dumps(BenchmarkSuiteResult.model_json_schema(), indent=2)[:400])
"

# 3. Implement run_release_gate against those shapes (Track A.1)
# 4. Wire the CLIs to call it (Track A.2)
# 5. Add make release-gate (Track A.3.b)
# 6. Write the e2e test (Track A.5)
# 7. Run make release-gate locally, inspect the report
# 8. Render the CHANGELOG entry from the report (Track A.4)
# 9. Commit + push to a branch + open the v0.5.0 PR
```

---

## 8. Why this plan is much narrower than the prior draft

The prior draft (revision 1) proposed adding an external benchmark
adapter module, a new CLI for downloading datasets, a governance
amendment around `huggingface.co`, and an off-CI reporting workflow.
All of that would have been **net-new design surface** invented to
solve a problem the design already answers.

This revision is **pure integration**: every file referenced exists,
every function called exists, every fixture used exists. The only new
artefacts are:

- One new function in `release/release_gate.py` (~50 LoC).
- A handful of small adapter helpers in the same file (~40 LoC).
- One new Makefile target.
- One new e2e test file.
- Optional: one or two fixtures appended to existing default lists.
- Optional: a small CHANGELOG-rendering script.

Total Track A + Track B deliverable size: **~150 lines of new code,
~100 lines of new tests, ~one paragraph of new Makefile**.

Track C is larger but is the natural follow-up after the loop is
closed.

---

## Appendix A — Why this is the right framing

The earlier framing was: *"the tool needs external benchmarks to be
considered production-ready"*. The design's framing is: *"the tool
needs to run its own release gate and stamp its numbers; the gate is
governance-compliant by construction; growth comes from production
usage of the tool itself"*.

Once that framing flip is accepted, the plan reduces from a multi-week
data-engineering project to a multi-day glue-coding project. The
result is also more aligned with Phase 18's stated goal: prove the
tool meets measurable quality thresholds **before** it is released —
not catch up to external benchmarks after the fact.
