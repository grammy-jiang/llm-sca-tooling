# Harness Drift Classifier

> Drift classes, detection rules, and response actions for the
> `local-agent-harness check` and `local-agent-harness validate` commands.

---

## Drift Classes

| Class | Meaning | Default response |
|---|---|---|
| `missing` | A required artefact for the current stage does not exist | Warn; block higher-autonomy work until resolved |
| `stale` | A required artefact exists but is outdated relative to its dependencies | Warn; treat as lower confidence |
| `relaxed` | A manifest, policy, or gate has been weakened relative to AGENTS.md or a lower stage | **Block** release and higher-autonomy work until reviewed |
| `out-of-stage` | A control is claimed but inconsistent with the assessed stage | Warn; include in readiness report |
| `clean` | No drift detected for this artefact | No action |

---

## Artefacts Subject To Drift Checking

- `AGENTS.md`
- All runtime overlays (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`)
- All `SKILL.md` templates under `.agent/skills/`
- Tool descriptions (MCP and CLI)
- CI workflow files under `.github/workflows/`
- `.pre-commit-config.yaml`
- Harness stage assessment record (`.agent/eval/stage-assessment.yaml`)
- AI-readiness report (`.agent/eval/readiness.md`)

---

## Relaxation Detection Rules

A drift of class `relaxed` must be reported when any of the following is true:

1. An HC1–HC6 constraint in `AGENTS.md` has been weakened or removed.
2. A verify-before-commit check that was previously required has been disabled
   without a reviewed waiver.
3. The path allowlist has been broadened beyond its previous scope without review.
4. A network deny rule has been removed.
5. A SAST, dependency, or secrets-scan gate has been disabled.
6. A stage-gating readiness threshold has been lowered.

---

## Stale Detection Rules

A drift of class `stale` is reported when:

1. `AGENTS.md` is missing a section that the current schema requires.
2. A runtime overlay does not declare `@AGENTS.md` precedence.
3. A `SKILL.md` template is missing required sections (Preconditions, Steps, Verify Gate, Completion Criteria).
4. The stage assessment record is older than 90 days without a newer record.
5. The readiness report has no machine block.

---

## Missing Detection Rules

A drift of class `missing` is reported when:

1. A required artefact for the current stage (S0+, S1+, etc.) does not exist.
2. `.secrets.baseline` is absent when `detect-secrets` is configured.
3. `Makefile` or `make verify` target is absent.

---

## Response Actions

| Drift class | Automated action | Manual action required |
|---|---|---|
| `missing` | `local-agent-harness init` renders the artefact | Review generated content |
| `stale` | `local-agent-harness refresh` (plan mode); `--apply` after review | Review diff before applying |
| `relaxed` | **None** — harness refuses to refresh | Remove HC-relaxing language; then re-run check |
| `out-of-stage` | Warn in report | Upgrade to correct stage or remove the out-of-stage claim |
| `clean` | None | None |

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | No drift detected (`clean`) |
| 1 | Drift detected (`missing`, `stale`, or `out_of_stage`) |
| 2 | `relaxed` drift detected — refresh blocked |

---

## Waivers

A `relaxed` or `stale` drift may be waived with a reviewed record:

```yaml
waiver_id: <id>
artefact: <path>
drift_class: relaxed | stale
reason: <justification>
owner: <name>
created_ts: <ISO-8601>
review_due_ts: <ISO-8601>
approved_by: <human name>
```

Waivers expire at `review_due_ts`. An expired waiver is treated as unreviewed drift.
