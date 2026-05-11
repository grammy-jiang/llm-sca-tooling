# Harness Setup Guide

> This guide covers writing `AGENTS.md`, configuring runtime overlays, setting permission
> profiles, running drift checks, and understanding the AI-readiness score.

---

## Limitations

- The harness enforces governance constraints but cannot prevent all misuse. Human review
  of `HarnessConditionSheet` artefacts is required for every release.
- Permission profiles are enforced by convention; enforcement requires agents that respect
  the profile. The harness records violations but cannot physically prevent them.
- The AI-readiness score is a heuristic index, not a guarantee of production quality.
- Harness drift detection is based on keyword and structural checks, not semantic
  understanding. A document that restates constraints in different words may not be
  detected as compliant.
- A `HarnessConditionSheet` must be completed for every evaluation and release run.

---

## 1. Writing `AGENTS.md`

`AGENTS.md` is the authoritative governance manifest. It must contain:

### Required sections

| Section | Purpose |
|---|---|
| Hard Constraints (HC1-HC6) | Non-relaxable rules for all agents |
| Scope Boundary | Write allowlist and excluded paths |
| Permission Modes | Six modes with capability tables |
| Command Allowlist | Permitted commands in execute mode |
| Verify-Before-Commit | The `make verify` / equivalent command |
| Stop Conditions | Doom-loop, out-of-scope write, HC violation |
| PR Checklist | Required checks before merging |

### HC1-HC6 summary

| ID | Rule |
|---|---|
| HC1 | No plaintext secrets in files, prompts, logs, or commits |
| HC2 | No agent writes outside the path allowlist |
| HC3 | Destructive commands require explicit human approval |
| HC4 | DB migrations and irreversible infrastructure changes must never run autonomously |
| HC5 | Network egress denied by default; only listed destinations allowed |
| HC6 | Red-class data (secrets, PII, credentials) must never enter prompts, logs, or artefacts |

### Minimal `AGENTS.md` template

```markdown
# AGENTS.md

## Hard Constraints
| ID | Rule |
|---|---|
| HC1 | No plaintext secrets in files, prompts, logs, or commits. |
| HC2 | No writes outside: src/, tests/, docs/, AGENTS.md, pyproject.toml |
| HC3 | Destructive commands require human approval before execution. |
| HC4 | DB migrations must never run autonomously. |
| HC5 | Network egress denied by default. Allowed: pypi.org, github.com (CI only). |
| HC6 | Red-class data must never enter prompts, logs, or artefacts. |

## Scope Boundary
Write allowlist: src/, tests/, docs/

## Verify-Before-Commit
Command: make verify

## Stop Conditions
- Doom-loop: same tool called 5× → stop and ask.
- Out-of-scope write: abort + revert.
- HC violation: stop immediately.
```

---

## 2. Runtime Overlays

Runtime overlays customize agent behavior for a specific agent or tool. They **must
not relax** HC1-HC6 or any quality gate declared in `AGENTS.md`.

| File | Agent | Must restate HC controls? |
|---|---|---|
| `CLAUDE.md` | Claude Code | No (may reference `@AGENTS.md`) |
| `.github/copilot-instructions.md` | GitHub Copilot (VS Code, PR reviews) | Yes |
| `.codex/INSTRUCTIONS.md` | OpenAI Codex CLI | Yes |

### Overlay authoring rules

- Overlays may add agent-specific tool allowlists or formatting preferences.
- Overlays may not weaken any hard constraint.
- A drift check that finds a weakened constraint in an overlay creates a `relaxed`
  drift finding, which blocks CI.

---

## 3. Permission Profiles and the Six Modes

| Mode | Read | Search | Edit | Execute | Review | Commit |
|---|---|---|---|---|---|---|
| `read_only` | ✓ | — | — | — | — | — |
| `read_search` | ✓ | ✓ | — | — | — | — |
| `read_search_edit` | ✓ | ✓ | ✓ | — | — | — |
| `read_search_execute` | ✓ | ✓ | — | ✓ | — | — |
| `review` | ✓ | ✓ | — | — | ✓ | — |
| `commit` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Setting the default mode

In your configuration:

```toml
[permissions]
default_mode = "read_search_edit"   # recommended for development
```

### Widening and drift

A profile change that widens permissions beyond the workspace default triggers a
harness drift `relaxed` finding. Widen profiles only after adding a reviewed waiver:

```yaml
# .agent/waivers/perm-widen-001.yaml
reason: "Temporary commit access for release automation"
owner: "alice@example.com"
expiry: "2026-06-01"
rollback: "Revert default_mode to read_search_edit"
```

---

## 4. Running Harness Drift Checks

```bash
llm-sca-tooling release check-drift .
# or with options:
llm-sca-tooling release check-drift . --fail-on relaxed
```

### Drift classifications

| Class | Meaning | CI action |
|---|---|---|
| `clean` | Present, current, non-relaxing | Pass |
| `stale` | Present but content is outdated | Warn (S2+: fail) |
| `missing` | Required for current stage but absent | Fail |
| `relaxed` | Weakens a hard constraint | Always fail |
| `out-of-stage` | Contains controls not yet appropriate | Warn |

`relaxed` drift always fails CI unless a reviewed waiver is present.

---

## 5. AI-Readiness Score: Five Axes

The readiness score (0-25) is computed across five axes:

| Axis | Max score | What is measured |
|---|---|---|
| Governance | 5 | AGENTS.md completeness and HC1-HC6 presence |
| Testing | 5 | Test coverage, CI integration, T1 gate passing |
| Documentation | 5 | User-facing guides present and complete |
| Security | 5 | SAST, secrets scan, dependency audit passing |
| Operations | 5 | Run records, incident tracking, drift checks |

### Stage thresholds

| Score | Stage | Meaning |
|---|---|---|
| 0-4 | S0 | Greenfield |
| 5-9 | S1 | Basic harness |
| 10-14 | S2 | CI integrated |
| 15-25 | S3 | Production-grade |

Check score with:
```bash
llm-sca-tooling harness status
# or via MCP:
run_readiness_audit()
```

---

## 6. Session Telemetry

What is recorded per session:

| Event type | What is stored |
|---|---|
| `session_start` | Session ID, timestamp, agent identity (no credentials) |
| `tool_call` | Tool name, args (redacted), result grade |
| `gate_result` | Gate name, pass/fail, evidence links |
| `budget_event` | Token count, wall-clock time, budget % used |
| `policy_decision` | Permission mode, allowed/denied, reason |
| `session_end` | Final status, budget consumed, run record reference |

What is **not** recorded:
- Source code content (only node IDs and file paths)
- LLM prompt content (only evidence summaries)
- Red-class data (HC6; redacted before any storage)

### Telemetry location

Telemetry JSONL files are written to `$EVIDENCE_SCA_WORKSPACE/telemetry/`.

---

## 7. Budget Configuration

```toml
[budget]
context_window_compact_threshold = 0.70    # compact at 70%
token_spend_warn = 200_000                 # warning threshold
token_spend_hard_stop = 250_000            # hard stop
wall_clock_warn_seconds = 1800             # 30 min warning
wall_clock_hard_stop_seconds = 2700        # 45 min hard stop
retry_per_tool_call = 3                    # retries before escalate
consecutive_identical_calls_limit = 5      # doom-loop threshold
```

---

## 8. Memory Opt-In

| Memory tier | What is stored | Default |
|---|---|---|
| Session plan | `.agent/plan.md` | Opt-in (agent writes it) |
| Lessons | `.agent/lessons/` | Opt-in (human reviews + promotes) |
| Readiness reports | `.agent/eval/` | Opt-in (harness writes on command) |

No red-class data is stored in any memory tier (HC6).

Memory that is not explicitly written is not retained between sessions.
The operational store retains run records and incidents per the workspace retention policy.

---

## Related Documents

- [Architecture Overview](architecture.md) — governance design and product surfaces.
- [Evaluation Guide](evaluation-guide.md) — benchmark tiers and calibration reports.
- [Incident Response Guide](incident-response-guide.md) — respond to HC violations and incidents.
