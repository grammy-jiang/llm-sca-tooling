# Evaluation Guide

> This guide explains the T1-T4 benchmark ladder, how to run evaluations,
> how to interpret calibration reports, and the mandatory reporting rules
> from Phase 18.

---

## Limitations

- Benchmark results are **not** a guarantee of production correctness. They establish
  calibration baselines; actual quality depends on repository characteristics.
- T1 null-mode results cannot be compared to T2+ LLM-mode results without separate
  calibration.
- Contamination canaries detect accidental test set memorization; they do not detect
  intentional adversarial tuning.
- The RDS v0.2 feature vector describes findings, not root causes. Two runs with
  identical RDS vectors may have different root causes.
- All calibration reports reference the Phase 18 evaluation run artefacts stored in
  the workspace. Do not interpret raw numbers without reading the associated
  `HarnessConditionSheet`.
- A `HarnessConditionSheet` must be completed for every evaluation run that claims
  a quality verdict.

---

## T1-T4 Benchmark Ladder

| Tier | Name | Description | LLM | Typical duration |
|---|---|---|---|---|
| **T1** | Smoke | Synthetic fixtures; null-mode only | No | Seconds |
| **T2** | Unit | Published benchmarks (SWE-bench-Live style) | Optional | Minutes |
| **T3** | Integration | Cross-language and multi-file fixtures | Yes | Minutes–hours |
| **T4** | Production | Live repositories; human review required | Yes | Hours |

### T1 (Smoke) — null mode

T1 is the minimum gate for every CI check. It uses only graph heuristics (no LLM calls),
so it runs without any API keys.

```bash
llm-sca-tooling release gate --suite t1 --null-mode
```

T1 checks:
- Graph build completes without errors.
- At least one evidence node is produced per fixture.
- No critical SAST findings in the smoke fixture set.
- Harness drift check passes.

### T2 (Unit) — published benchmarks

T2 runs against a subset of SWE-bench-Live style fixtures with known ground truth.

```bash
llm-sca-tooling release gate --suite t2
# Requires LLM_API_KEY
```

T2 metrics: correctness rate, evidence coverage, false-positive rate.

### T3 (Integration)

T3 validates cross-language and plugin-generated evidence chains.

```bash
llm-sca-tooling release gate --suite t3
```

### T4 (Production)

T4 runs against live repositories with human reviewer sign-off.
Not automated; requires manual `HarnessConditionSheet` completion.

---

## Running a Smoke Eval

```bash
# 1. Ensure graph is built
graph_build(repo_path=".")  # via MCP client

# 2. Run T1 in null mode
llm-sca-tooling release gate --suite t1 --null-mode

# 3. Inspect the report
llm-sca-tooling harness status
```

Expected output (passing):
```
T1 smoke eval: PASS
Null mode: yes
Evidence nodes: N
Gate result: PASS
```

---

## Adding Local Smoke Fixtures

Create a fixture file in `tests/eval/fixtures/`:

```python
# tests/eval/fixtures/my_smoke_fixture.py
from llm_sca_tooling.eval.fixture_base import SmokeFixture

class MySmoke(SmokeFixture):
    fixture_id = "my-smoke-001"
    repo_path = "tests/fixtures/my_repo"  # directory with test source files
    expected_min_evidence_nodes = 3
    expected_no_critical_sast = True
```

Run only your fixture:
```bash
uv run pytest tests/eval/ -k "my-smoke-001" -x
```

---

## Interpreting Calibration Reports

A calibration report (from `run_readiness_audit` or `run_operational_review`) contains:

| Field | Meaning |
|---|---|
| `score` | AI-readiness score (0-25, five axes × 0-5) |
| `harness_stage` | S0-S3 stage classification |
| `drift_findings` | List of detected harness drift issues |
| `gate_results` | Pass/fail for each deterministic gate |
| `evidence_coverage` | % of fixtures with at least one evidence node |
| `false_positive_rate` | % of findings with no ground-truth match |

**Score interpretation:**

| Score | Stage | Meaning |
|---|---|---|
| 0-4 | S0 | Greenfield; harness not yet configured |
| 5-9 | S1 | Basic harness; no CI or SAST integration |
| 10-14 | S2 | CI integrated; some drift present |
| 15-25 | S3 | Production-grade; all gates passing |

---

## Mandatory Reporting Rules (Phase 18)

Every evaluation run must include all eight of the following in its report:

1. **eval_tier**: T1, T2, T3, or T4.
2. **null_mode**: whether LLM was used.
3. **evidence_coverage**: % of fixtures producing at least one evidence node.
4. **calibration_run_id**: reference to the Phase 18 calibration baseline.
5. **false_positive_rate**: % of findings with no ground-truth match.
6. **correctness_rate**: % of findings matching ground truth (T2+ only; `null` for T1).
7. **contamination_canary_result**: `pass | fail | not_run`.
8. **harness_condition_id**: the `HarnessConditionSheet` identifier for this run.

Missing any of these fields causes the run to be rejected as incomplete evidence.

---

## Understanding Contamination Canaries

Contamination canaries are synthetic fixtures designed to detect accidental test set
memorization by LLMs:

- Canary fixtures contain deliberate errors that a memorizing model would reproduce.
- A canary `fail` result means the model reproduced a canary error; the run is suspect.
- Canary `pass` does not guarantee no memorization, only that these specific patterns
  were not reproduced.

Run canary checks with:
```bash
llm-sca-tooling release gate --suite t2 --run-canaries
```

---

## RDS v0.2 Feature Vector

The RDS (Risk Description Score) v0.2 feature vector describes each finding along
seven dimensions:

| Feature | Values | Meaning |
|---|---|---|
| `evidence_grade` | parser/analyser/heuristic/unknown | Source of the finding |
| `blast_radius` | low/medium/high | Number of affected callers/callees |
| `sast_severity` | info/warning/error/critical | Underlying SAST grade if present |
| `test_coverage` | covered/uncovered/unknown | Whether a test covers this code path |
| `change_recency` | recent/stable/unknown | Last commit age (recent = <30 days) |
| `cross_language` | yes/no | Whether a cross-language edge is involved |
| `plugin_evidence` | yes/no | Whether plugin-generated evidence is included |

Use RDS vectors to:
- Compare findings across runs (same vector = likely same issue, different run).
- Filter findings by severity (e.g., show only `critical` SAST + `high` blast radius).
- Track calibration drift over time (RDS distribution shift = model behavior change).

---

## Related Documents

- [Architecture Overview](architecture.md) — evidence hierarchy and benchmark framework design.
- [Harness Setup Guide](harness-setup-guide.md) — configure gates and permission profiles.
- [Incident Response Guide](incident-response-guide.md) — respond to calibration regressions.
