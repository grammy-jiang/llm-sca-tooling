# AGENTS.md

> Governance manifest for the LLM-SCA tooling repository.
> This file is the authoritative source for hard constraints, scope, quality
> gates, and the local-agent development contract. Runtime overlays
> (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`)
> may specialize but must never relax the rules declared here.
>
> **Non-relaxation declaration**: any runtime overlay that contradicts this
> file on HC1–HC6 or any quality gate is invalid and will be rejected by
> drift checking and CI governance.
>
> Phase: H0 — Harness Quality Foundation

<!-- local-agent-harness:auto:begin -->
<!-- stack: Python -->
## Setup

```bash
pip install -e '.[dev]'  # or: uv sync
```

## Build

```bash
# see Makefile for available tasks
```

## Testing

```bash
pytest
pytest path/to/test_file.py::test_function_name
```

## Lint and Format

```bash
ruff check src tests
mypy src  # strict mode
ruff format src tests
```

## Code Style

- Line length: 88
- mypy --strict enforced on src/
- Target Python: py312

<!-- local-agent-harness:auto:end -->

---

## Hard Constraints

All constraints are enforced at every harness stage and must never be relaxed.

| ID | Rule |
|---|---|
| **HC1** | No plaintext secrets in repository files, prompts, logs, or commits. `detect-secrets` pre-commit hook and `.secrets.baseline` are required. |
| **HC2** | No agent-authored writes outside the path allowlist in § Scope Boundary. Out-of-scope writes must be denied, reverted, and recorded as policy violations. |
| **HC3** | Destructive commands (`rm -rf`, `git push --force`, `git reset --hard`, schema drops, package publishes, `DROP TABLE`) require explicit human approval before execution. |
| **HC4** | Database migrations, schema drops, and irreversible infrastructure changes must be authored but never executed autonomously. |
| **HC5** | Network egress is denied by default. Only explicitly listed destinations may be accessed from agent-executed code. |
| **HC6** | Red-class data (secrets, PII, credentials, session tokens, customer data) must never enter prompts, tool arguments, trace logs, plan files, or stored artefacts. |

Allowed network egress:
- `pypi.org`, `files.pythonhosted.org` — package downloads (CI only)
- `github.com` — source retrieval and CI operations (CI only)

All other destinations are denied. MCP server calls to external services require
an explicit allow entry here with justification.

---

## Success Definition

A task is successfully completed when:

1. `make verify` exits 0.
2. All changes are within the declared scope boundary.
3. No hard constraint was violated during the session.
4. A session plan (`.agent/plan.md`) was written and updated.
5. For evaluation or release runs: a completed Harness Condition Sheet exists.
6. No red-class data entered prompts, logs, or stored artefacts.
7. The AI-readiness report shows no per-axis regression (or a reviewed waiver exists).

**Feature acceptance requires**: a completed Harness Condition Sheet, a session
trace, and a passing verify path. Demo runs without these artefacts are not
accepted as evidence of completion. See § Local-Agent Development Contract.

---

## Scope Boundary

### Write Allowlist

| Path | Allowed operations |
|---|---|
| `src/` | Create, edit (Phase 0+) |
| `tests/` | Create, edit |
| `schemas/` | Create, edit |
| `docs/` | Create, edit |
| `.agent/` | Create, edit (plan, skills, templates, docs, eval) |
| `.agents/skills/` | Create, edit (Agent Skills standard — discoverable by Copilot CLI, VS Code, Claude Code) |
| `AGENTS.md` | Edit (requires governance review) |
| `CLAUDE.md` | Edit |
| `pyproject.toml` | Edit |
| `tox.ini` | Edit |
| `Makefile` | Edit |
| `.pre-commit-config.yaml` | Edit (requires governance review) |
| `.github/workflows/` | Edit (requires governance review) |

### Explicitly Excluded

| Path | Reason |
|---|---|
| `.git/` | Git internals — never write |
| `.env`, `.env.*` | Secrets |
| `*.key`, `*.pem` | Secrets |
| `credentials/`, `secrets/` | Secrets |

Operations outside the write allowlist require explicit human approval.
HC2 blocks silent out-of-scope writes; any such attempt must be aborted,
reverted, and recorded.

---

## Data Policy

| Class | Examples | In prompts? | In logs? | In artefacts? |
|---|---|---|---|---|
| Green | OSS source, public docs, test fixtures | Yes | Yes | Yes |
| Amber | Internal source, non-PII configs, issue text | Yes (redact tokens) | Redacted | Redacted |
| Red | Secrets, PII, credentials, session tokens, customer data | **No** | **No** | **No** |

Redaction rules:
- Any string matching a `detect-secrets` pattern must be treated as Red-class.
- Amber-class fields must be hash-only or redacted in session traces.
- Every trace event must carry a `redaction_status` field (see § Telemetry Contract).

HC6 is unconditional: Red-class data must not enter the system under any circumstances.

---

## Quality Gate

All of the following must pass before a task is declared complete or a PR is opened:

1. `make verify` exits 0.
2. No new secrets detected by `detect-secrets`.
3. No high/critical SAST findings (required from S1).
4. No critical CVE findings from `pip-audit` (required from S1).
5. AI-readiness report shows no per-axis regression without a reviewed waiver.
6. Manifest regression tests pass (required from S1).
7. `local-agent-harness check --repo .` exits 0.

---

## Cost Policy

| Budget | Limit | Action on breach |
|---|---|---|
| Context window | 70 % before compaction | Compact; retain AGENTS.md, plan.md, last 5 tool calls, open diff |
| Token spend per session | 200 000 tokens | Emit `budget_warning` |
| Token hard stop | 250 000 tokens | Stop session; record `budget_hard_stop` event |
| Wall-clock per session | 30 min | Emit `budget_warning` |
| Wall-clock hard stop | 45 min | Stop session |
| Retry per tool call | 3 attempts | Stop and escalate to human |
| Consecutive identical calls | 5 | Stop and ask (doom-loop check) |

---

## Tool Categories And Permissions

### Categories

| Category | Examples | Default mode |
|---|---|---|
| `read` | File read, symbol lookup, repo query | Allowed in all modes |
| `search` | Grep, glob, semantic search | Allowed in all modes |
| `edit` | File edit, schema change, test creation | Requires `scoped-edit` or explicit path scope |
| `execute` | Shell commands, test runner, formatter, linter, SAST | Requires `scoped-execute` and command allowlist |
| `review` | Patch review, diff analysis, gate evaluation | Allowed in `review/commit` mode |
| `commit` | Git commit, PR creation, tag | Requires human approval or `review/commit` mode with passing gates |

### Permission Modes

| Mode | Allowed categories | When to use |
|---|---|---|
| `read-only` | `read`, `search` | Ambiguous or security-sensitive tasks |
| `plan` | `read`, `search`, `.agent/plan.md` write | Session planning only |
| `scoped-edit` | `read`, `search`, `edit` within path scope | After scope and commands confirmed in plan |
| `scoped-execute` | `read`, `search`, `edit`, `execute` within allowlist | After test and verify commands are known |
| `review-commit` | All categories | After all deterministic gates pass |

Never use broad bypass modes for CI, releases, or shared repositories.

### Command Allowlist

Allowed in `scoped-execute` mode:

```
uv run isort .
uv run isort --check .
uv run black .
uv run black --check .
uv run ruff check .
uv run ruff check . --fix
uv run mypy src/
uv run pytest tests/ -x
uv run pytest tests/unit/ -x
uv run pytest tests/harness/ -x
uv run pip-audit
uv run bandit -r src/ -c pyproject.toml
uv run lint-imports
uv run detect-secrets scan
uv run detect-secrets audit .secrets.baseline
make verify
make verify-fast
make verify-docs
make verify-format
make verify-lint-imports
make verify-types
make verify-tests
make verify-security
make verify-dirty
local-agent-harness check --repo .
local-agent-harness assess --repo . --json
local-agent-harness validate --repo .
local-agent-harness report --repo . --out .agent/eval/readiness.md
git status
git diff
git log --oneline -20
git add <specific-file>
git commit -m <message>
git checkout -b agent/<task-slug>
```

Destructive commands (HC3) require explicit human approval before execution.

---

## Verify-Before-Commit

```
verify:
  command: make verify
  phases:
    - verify-format      # isort, black, ruff
    - verify-lint-imports
    - verify-types       # mypy strict
    - verify-tests       # unit + harness
    - verify-security    # detect-secrets (non-mutating), pip-audit, bandit
    - verify-dirty       # assert uv.lock and .secrets.baseline unchanged
  equivalent: |
    uv run --frozen isort --check . &&
    uv run --frozen black --check . &&
    uv run --frozen ruff check . &&
    uv run --frozen lint-imports &&
    uv run --frozen mypy src/ &&
    uv run --frozen pytest tests/unit/ -x &&
    uv run --frozen detect-secrets scan > /tmp/s.json && python3 -c "<compare>" &&
    uv run --frozen pip-audit &&
    uv run --frozen bandit -r src/ -c pyproject.toml
  must_pass_before: commit, PR creation, release gate
  notes: >
    Steps requiring Phase 0+ artefacts (src/, tests/unit/) are skipped
    gracefully at S0. See Makefile for the conditional logic.
    All verify-path commands use --frozen to prevent uv.lock mutations.
    detect-secrets is run non-mutating: scans to a temp file and compares
    hashes to the existing baseline; .secrets.baseline is never rewritten.
    A dirty-check gate runs last to catch any unexpected file mutations.
```

### Scanner phase timeouts

`detect-secrets`, `pip-audit`, and `bandit` are intentionally quiet while
scanning. Each phase emits `[verify] start <phase>` and
`[verify] done  <phase> elapsed=Xs` lines. Use these to distinguish
"still scanning" from "hung":

| Threshold | Action |
|---|---|
| < 10 min silent, process alive, last line was a scanner | Treat as normal; wait |
| ≥ 10 min (soft timeout) | Log as slow; check process liveness |
| ≥ 15 min (hard timeout) | Escalate; do not declare a stall until process dead |

For fast iteration (no security or tests), use `make verify-fast`.
For docs-only changes, use `make verify-docs` (formatting only).

Run `make verify` before every commit. The command must exit 0.
Activate pre-commit hooks after cloning: `pre-commit install`.
See `Makefile` and `.pre-commit-config.yaml` for canonical implementations.

---

## Local-Agent Development Contract

For non-trivial work, an agent operating in this repository must:

1. Read current `AGENTS.md` and the applicable `SKILL.md`.
2. Write a `.agent/plan.md` covering scope, commands, expected outputs, and risks.
3. Read current evidence (tests, CI state, graph) rather than relying on prior session memory.
4. Edit only within the declared scope.
5. Run `make verify` before claiming work is done.
6. Record verification results in the plan or a linked run-record event.
7. Summarize remaining risk and uncertainty in the closing summary.

This contract applies to the development process itself, not only the final product.

---

## Memory Governance

| Tier | Location | Contents | Retention |
|---|---|---|---|
| Session | `.agent/plan.md` | Current scope, steps, decisions log | Single session |
| Project | `.agent/lessons/` | Reviewed and promoted lessons | Until retired |
| Artefact | `.agent/eval/` | Readiness reports, stage assessments | Persistent, versioned |

Rules:
- Session memory is ephemeral and must be reset at session start.
- Lessons must be reviewed before promotion to `.agent/lessons/`.
- No red-class data in any memory tier (HC6).
- Schema-grounded: every stored event must carry `event_id`, `session_id`, `ts`, and `type`.

---

## Lesson Promotion Policy

A lesson may be promoted from `.agent/plan.md` to `.agent/lessons/` when:

1. A human has reviewed and confirmed the lesson.
2. The lesson is generalizable (applies across sessions or tasks).
3. The lesson contains no red-class data.
4. The lesson has a clear title, body, `origin_run_id`, and `promoted_by` field.

Lesson format:

```yaml
title: <short title>
body: <explanation>
origin_run_id: <run_id or session reference>
promoted_by: human
promoted_ts: <ISO-8601>
applies_to: <feature area or all>
```

Superseded lessons must be marked `retired: true` and kept for audit.

---

## Telemetry Contract

Session telemetry must be live — emitted while the session runs, not reconstructed
after failure. A file-based JSONL writer is sufficient.

See `.agent/docs/telemetry-contract.md` for full event types and required fields.

A session with no `session_end` event is incomplete. A session that produced commits
or PRs without a passing `verification_event` is a policy violation.

---

## Run-Record Contract

Every product workflow must emit a run record.
See `.agent/docs/run-record-contract.md` for required fields.

A run claiming a positive verdict must have `trace completeness: complete`
and a `harness_condition_id`.

---

## References

- `.agent/docs/telemetry-contract.md` — live telemetry event types and required fields
- `.agent/docs/run-record-contract.md` — run record and run event fields
- `.agent/docs/ai-readiness-rubric.md` — five-axis scoring rules and stage thresholds
- `.agent/docs/drift-classifier.md` — drift classes, detection rules, and response actions
- `.agent/docs/supply-chain-policy.md` — lockfile, tool-inventory, and provenance policy
- `.agent/templates/harness-condition-sheet.md` — required for every evaluation and release run
- `.agent/templates/incident-record.md` — required for P0/P1 operational failures
- `.agent/templates/operational-review.md` — post-run review template
- `.agents/skills/` — Agent Skills standard skills (auto-discovered by Copilot CLI, VS Code Copilot, Claude Code); each skill is a subdirectory containing `SKILL.md` with YAML frontmatter
- `.agent/skills/` — legacy skill markdown files (superseded by `.agents/skills/`; kept for reference)

---

## Conventions

- Branch naming: `agent/<task-slug>`
- Commit style: Conventional Commits
- Keep functions small and single-purpose.
- Match the existing code style and patterns.
- Prefer explicit error handling over silent failures.
- Run `make verify` after every change.
- Never push directly to `main`; open a pull request.
- `.gitignore` has a managed section — do not hand-edit it.

---

## Stop Conditions

- **Doom-loop**: same tool called 5× with similar args → stop and ask.
- **Out-of-scope write**: abort + revert + record as policy violation.
- **HC violation**: stop immediately; do not proceed until resolved.
- **Relaxed drift detected**: stop; surface the offending file and pattern; refuse
  to `refresh --apply` until cleared.
- **Secrets committed**: stop; ask the user to rotate and rewrite history before continuing.

---

## PR Checklist

1. All tests pass; add tests for every new function and every bug fix.
2. `make verify` exits 0.
3. No new secrets or SAST findings.
4. PR description includes: change summary, risks, verification evidence, dependency changes.
5. Keep PRs small and focused; split unrelated changes.
6. Append a `Decisions log` entry in `.agent/plan.md` for non-trivial choices.
7. Feature acceptance: include Harness Condition Sheet reference, session trace location, and verify command output.
8. `local-agent-harness check --repo .` exits 0.
