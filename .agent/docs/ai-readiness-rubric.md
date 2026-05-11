# AI-Readiness Rubric

> Five-axis rubric used by `local-agent-harness` to produce the readiness
> score in `.agent/eval/readiness.md`. Scores must not regress silently;
> see § No-Regression Rule.

---

## Five Axes (0–5 each, 25 total)

| Axis | What it measures | Max |
|---|---|---|
| `agent_config` | Quality of AGENTS.md, runtime overlays, plan template, skill templates, and tool/permission model | 5 |
| `documentation` | Architecture docs, quickstart, constraint explanations, limitation notes | 5 |
| `ci_cd` | CI pipeline coverage (lint, tests, secrets, SAST, dependency, manifest regression), release automation | 5 |
| `code_structure` | Typed models, schema exports, modularity, test coverage, no unsafe patterns | 5 |
| `security` | Secret scanning, SAST, dependency audit, path/network policy, redaction | 5 |
| **Total** | | **25** |

---

## Scoring Criteria Per Axis

### agent_config

| Score | Criteria |
|---|---|
| 0 | No AGENTS.md |
| 1 | AGENTS.md exists with at least HC1–HC6 |
| 2 | + plan template + at least one runtime overlay |
| 3 | + tool categories + permission modes + command allowlist |
| 4 | + skill templates (≥3) + cost policy + memory governance |
| 5 | + lesson promotion policy + full telemetry/run-record contract references |

### documentation

| Score | Criteria |
|---|---|
| 0 | No project documentation |
| 1 | At least one architecture document exists |
| 2 | + quickstart or README with setup instructions |
| 3 | + constraint explanations and limitation notes |
| 4 | + ADR log or decision records |
| 5 | + operational runbook + known limitations table |

### ci_cd

| Score | Criteria |
|---|---|
| 0 | No CI configuration |
| 1 | CI workflow exists and runs |
| 2 | + lint and format checks in CI |
| 3 | + test runner in CI |
| 4 | + secrets scan + dependency audit in CI |
| 5 | + manifest regression + SAST + release automation |

### code_structure

| Score | Criteria |
|---|---|
| 0 | No source files |
| 1 | Source files exist with basic structure |
| 2 | + type hints throughout |
| 3 | + schema exports or typed models |
| 4 | + test coverage ≥ 80 % |
| 5 | + test coverage ≥ 95 % core + no unsafe patterns |

### security

| Score | Criteria |
|---|---|
| 0 | No security tooling |
| 1 | `.gitignore` with secrets patterns + pre-commit configured |
| 2 | + detect-secrets baseline committed |
| 3 | + SAST (bandit) configured |
| 4 | + dependency audit (pip-audit) in CI |
| 5 | + path/network policy enforced + redaction policy documented |

---

## Stage Gate Thresholds

| Transition | Minimum total | Minimum per axis |
|---|---|---|
| S0 → S1 | 5 | 1 |
| S1 → S2 | 12 | 2 |
| S2 → S3 | 18 | 3 |
| Stable S3 | 22 | 4 |

---

## No-Regression Rule

A harness change fails the readiness no-regression check unless either:

- No per-axis readiness score decreases, OR
- The decrease is tied to an explicit reviewed waiver recording the reason,
  owner, and review-due date.

An AI-readiness report must include the previous report reference and a
per-axis delta. Compare using:

```
local-agent-harness report --repo . --check-no-regression .agent/eval/readiness.md
```

---

## Report Format

The readiness report at `.agent/eval/readiness.md` must include a machine block:

```
<!-- local-agent-harness:readiness:v1 -->
```

```
stage=<S0|S1|S2|S3>
total=<0-25>
agent_config=<0-5>
documentation=<0-5>
ci_cd=<0-5>
code_structure=<0-5>
security=<0-5>
```

The machine block enables automated regression detection across runs.
