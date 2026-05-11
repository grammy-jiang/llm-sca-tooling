# SKILL: release

Prepare and gate a package release with T1–T4 eval, readiness, and incident checks.

---

## Preconditions

- All planned features for the release are merged and green in CI.
- `make verify` passes on the release branch.
- No open P0 or P1 incidents.
- No `relaxed` drift detected: `local-agent-harness check --repo .` exits 0.

---

## Steps

### Pre-flight

1. **Check incident log**: confirm no open P0/P1 incidents.
2. **Run drift check**: `local-agent-harness check --repo .` must exit 0.
3. **Run readiness no-regression**: `make harness-report` exits 0.
4. **Copy and fill HCS**: `cp .agent/templates/harness-condition-sheet.md
   .agent/eval/hcs-release-<version>.md`; fill all fields.

### Evaluation Gates (T1–T4)

| Tier | Gate | Must pass? |
|---|---|---|
| T1 | `make verify` (format, lint, type check, unit tests, secrets, SAST, audit) | Yes |
| T2 | `uv run pytest tests/harness/ -x` (manifest regression + non-relaxation) | Yes |
| T3 | Integration tests (Phase 2+) | Yes (S2+) |
| T4 | Evaluation benchmark suite (Phase 3+) | Yes (S3) |

### Release Steps

5. **Run T1 gate**: `make verify`.
6. **Run T2 gate**: `uv run pytest tests/harness/ -x`.
7. **Run T3/T4 gates** if applicable.
8. **Record all gate results** in the HCS.
9. **Write session trace** and fill HCS Telemetry section.
10. **Bump version** in `pyproject.toml` and commit.
11. **Tag the release**: `git tag v<version>` (requires human approval — HC3).
12. **Produce operational review**: fill `.agent/templates/operational-review.md`.
13. **Publish** (requires human execution — HC3/HC4).
14. **Update the supply-chain ledger** with the new release version.

---

## Verify Gate

```
make verify
uv run pytest tests/harness/ -x
local-agent-harness check --repo .
local-agent-harness report --repo . --check-no-regression .agent/eval/readiness.md
```

---

## Completion Criteria

- All T1–T4 gates pass (T3/T4 only if applicable for the stage).
- HCS is complete; trace completeness is `complete`.
- No open P0/P1 incidents.
- Drift check exits 0.
- Readiness no-regression passes.
- Tag and publish required human approval (HC3); not executed autonomously.
- Operational review filed and committed.
