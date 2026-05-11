# Run-Record Contract

> Phase H0 defines this contract. Phase 4A implements the runtime tools.
> A parseable run-record schema must exist before workflow implementation
> begins, even if the first writer is file-based.
>
> See also: `schemas/run-record.schema.json`

---

## Run Record Required Fields

```
run_id               string   — high-entropy, non-guessable identifier
workflow             string   — e.g. "bug-resolve", "patch-review", "implementation-check"
user_intent_hash     string   — hash of the user-provided issue or request
repos                array    — list of repo IDs involved in this run
start_ts             string   — ISO-8601 UTC
end_ts               string?  — ISO-8601 UTC or null if still running
status               string   — running | complete | failed | incomplete |
                                unknown | budget-exhausted
model_backend        string   — model name and version string
toolset_hash         string   — hash of active MCP tools and versions
policy_id            string   — identifier of the active policy document
permission_profile   string   — read-only | plan | scoped-edit |
                                scoped-execute | review-commit
context_budget       integer? — token budget limit, or null if not set
run_event_count      integer  — count of run events emitted
harness_condition_id string?  — ID of the linked HCS, or null
final_verdict_id     string?  — ID of the final verdict artefact, or null
incident_ids         array    — list of incident IDs opened during this run
redaction_policy     string   — policy name applied to all fields and events
```

---

## Run Event Required Fields

```
event_id             string   — unique within run
run_id               string   — links to the parent run record
seq                  integer  — monotonically increasing within run, starting at 1
ts                   string   — ISO-8601 UTC
type                 string   — tool_call | gate | context | budget | compaction |
                                approval | denial | monitor | review | incident | promotion
actor                string   — human | agent | tool | system
stage                string   — planning | investigation | editing | execution |
                                verification | review | commit | unknown
input_ref            string?  — artefact ID or null
output_ref           string?  — artefact ID or null
policy_action        string   — allow | deny | approval_required | blocked |
                                checkpoint | force_unknown | not_applicable
token_count          integer? — tokens consumed, or null
wall_ms              integer? — wall-clock duration in milliseconds, or null
artefact_ids         array    — list of artefact IDs produced or consumed
redaction_status     string   — not_required | redacted | hash_only | blocked | unknown
```

---

## Run-Record Invariants

- Run events are append-only and sequence-numbered.
- A run with `status: complete` must have a `harness_condition_id` and a `final_verdict_id`.
- A run with `status: budget-exhausted` must have its last event be of type `budget_hard_stop`.
- A run without a `session_end` or `verification_event` covering the declared verify path
  is `incomplete`.
- Incidents and promotion candidates must reference a source `run_id` and `event_id`.

---

## Storage

Run records are stored under `.agent/runs/<run_id>/`:

```
.agent/runs/<run_id>/
  run-record.json    — the run record
  events.jsonl       — run events (append-only, one JSON object per line)
  hcs.md             — copy of the Harness Condition Sheet for this run
```

Run directories are excluded from git. Export to a separate store before deletion
if audit retention is required.
