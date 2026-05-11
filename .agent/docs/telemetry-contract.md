# Telemetry Contract

> Session telemetry must be live — emitted while the session runs, not
> reconstructed after failure. A file-based JSONL writer is sufficient for
> Phase H0. The writer appends one JSON object per line to
> `.agent/traces/<session_id>.jsonl`.

---

## Required Event Types

| Event type | When emitted |
|---|---|
| `session_start` | Session begins |
| `session_end` | Session closes (normally or by timeout) |
| `plan_created` | `.agent/plan.md` is written |
| `plan_updated` | `.agent/plan.md` is modified |
| `tool_call` | Any tool is invoked |
| `tool_result` | Tool invocation completes |
| `context_assembled` | Context window is assembled for a prompt |
| `compaction_event` | Context is compacted |
| `cost_checkpoint` | Token/cost checkpoint recorded |
| `diff_snapshot` | A code diff is captured after edits |
| `verification_event` | A verify step completes (pass, fail, or skip) |
| `human_approval` | A human approves an action |
| `human_rejection` | A human rejects an action |
| `policy_decision` | A policy allow/deny/approval-required decision |
| `budget_warning` | A soft budget threshold is crossed |
| `budget_hard_stop` | A hard budget threshold is crossed |

---

## Base Fields (every event)

```
event_id         string   — non-empty, unique within session
session_id       string   — identifies the session this event belongs to
seq              integer  — monotonically increasing within session, starting at 1
ts               string   — ISO-8601 UTC timestamp
type             string   — one of the event types above
actor            string   — human | agent | tool | system
stage            string   — planning | investigation | editing | execution |
                            verification | review | commit | unknown
redaction_status string   — not_required | redacted | hash_only | blocked | unknown
```

---

## Additional Fields: tool_call and tool_result

```
tool_name        string   — name of the tool invoked
tool_category    string   — read | search | edit | execute | review | commit
policy_action    string   — allow | deny | approval_required | blocked | not_applicable
input_ref        string?  — artefact ID or null
output_ref       string?  — artefact ID or null
token_count      integer? — tokens in prompt + completion, or null
wall_ms          integer? — wall-clock duration in milliseconds, or null
```

---

## Additional Fields: verification_event

```
check_name       string   — name of the verify step (e.g. "make verify", "pytest")
outcome          string   — pass | fail | skip | unknown
artefact_ids     array    — list of artefact IDs produced by this step
```

---

## Invariants

- Events are append-only. Existing events must not be modified.
- `seq` must be strictly monotonically increasing within a session.
- A session with no `session_end` event is incomplete for operational review purposes.
- A session that produced commits or PRs without a passing `verification_event`
  is a policy violation.
- `redaction_status` must be set; `unknown` is a last resort and must be
  accompanied by a human review note.

---

## File Layout

```
.agent/
  traces/
    <session_id>.jsonl   — one JSON object per line; append-only
```

Trace files are excluded from git (listed in `.gitignore`).
For audit purposes, traces may be exported to a separate store before deletion.

---

## Minimal JSONL Example

```json
{"event_id":"e1","session_id":"s1","seq":1,"ts":"2026-05-09T12:00:00Z","type":"session_start","actor":"agent","stage":"planning","redaction_status":"not_required"}
{"event_id":"e2","session_id":"s1","seq":2,"ts":"2026-05-09T12:00:01Z","type":"plan_created","actor":"agent","stage":"planning","redaction_status":"not_required"}
{"event_id":"e3","session_id":"s1","seq":3,"ts":"2026-05-09T12:05:00Z","type":"tool_call","actor":"agent","stage":"editing","redaction_status":"not_required","tool_name":"Edit","tool_category":"edit","policy_action":"allow","input_ref":null,"output_ref":null,"token_count":null,"wall_ms":null}
{"event_id":"e4","session_id":"s1","seq":4,"ts":"2026-05-09T12:05:01Z","type":"tool_result","actor":"tool","stage":"editing","redaction_status":"not_required","tool_name":"Edit","tool_category":"edit","policy_action":"allow","input_ref":null,"output_ref":"artefact:file:src/foo.py","token_count":null,"wall_ms":120}
{"event_id":"e5","session_id":"s1","seq":5,"ts":"2026-05-09T12:10:00Z","type":"verification_event","actor":"agent","stage":"verification","redaction_status":"not_required","check_name":"make verify","outcome":"pass","artefact_ids":[]}
{"event_id":"e6","session_id":"s1","seq":6,"ts":"2026-05-09T12:10:01Z","type":"session_end","actor":"agent","stage":"verification","redaction_status":"not_required"}
```
