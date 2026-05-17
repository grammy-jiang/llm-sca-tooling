# LLM-SCA Tooling Phase H0 Implementation Plan: Harness Quality Foundation

> Date: 2026-05-09
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase H0 - Harness Quality Foundation
> Primary objective: establish the operational envelope — manifests, permission profiles, telemetry contracts, verify-before-commit gates, harness stage/drift classification, and AI-readiness scoring — before any product feature is implemented. This phase is both a development process requirement and a product requirement, and it stays active through every later phase.

---

## 1. Phase Summary

Phase H0 creates the governance substrate for the LLM-SCA tooling project. It does not implement product features. It establishes the standards, structures, and contracts that determine whether later feature work can be operated, audited, bounded, evaluated, and improved under real conditions.

The central rule for this phase is:

```text
No feature phase is complete unless it can declare a Harness Condition Sheet, produce a
session trace, pass the local verify command, and demonstrate compliance with the
permission and policy model defined here.
```

Phase H0 must hold these principles from the source plan:

- The harness is part of the product, not only development scaffolding.
- Policies, permissions, telemetry, verification, memory, and evaluation must be versioned and testable.
- Observability must be live, not reconstructed after failure.
- Policy enforcement belongs in deterministic code; LLM summaries can explain a violation but cannot waive one.
- Harness drift of class `relaxed` blocks release and higher-autonomy work until reviewed.
- AI-readiness must be assessed on five axes and must not regress silently.

The harness quality formula from the local-agent guide applies here:

```text
good output = correct behaviour + maintainable structure + policy compliance + traceable process
```

### Architecture Coverage

Phase H0 covers:

- F0 - Harness quality substrate
- Development-time and product-time governance
- Release-quality definition for all later phases
- H0 through H10 harness controls as enumerated in §1.1 of the implementation plan
- Local-Agent Development Contract from §1.3 of the implementation plan

### Inherited Paper Anchors

Use these anchors in issues, ADRs, PR descriptions, and benchmark reports that derive from this phase:

- `opendev`
- `agenttrace`
- `aer`
- `runtime-governance`
- `workstream`
- `tdad`
- `needle-repo`
- `schema-grounded-memory`
- `agentic-harness-engineering`

Do not overuse paper anchors in source-code comments. Comments should explain non-obvious implementation choices, not reproduce the research registry.

## Technology Stack

This phase establishes the development and governance toolchain from `llm-sca-tooling-tech-stack.md`. No product libraries are introduced here — only the tools that enforce quality, security, and harness compliance throughout every subsequent phase.

| Tool | Version | Role in this phase |
|---|---|---|
| `pre-commit` | >=3.7 | Git hook framework; secrets scan, format, lint run on every commit |
| `detect-secrets` | >=1.5 | HC1 enforcement: blocks commits that introduce new secret patterns; `.secrets.baseline` committed to repo |
| `pip-audit` | >=2.7 | HC1 dependency vulnerability scanning; CI gate on every pull request |
| `bandit` | >=1.7 | Code quality SAST for Python AST security patterns; runs in verify pipeline |
| `isort` | >=5.13 | Import sorting; runs before black in verify sequence |
| `black` | >=24.0 | Code formatting; line length 88 |
| `ruff` | >=0.4 | Linting only (formatter disabled); runs after black |
| `mypy` | >=1.10 | Static type checking with `pydantic-mypy` plugin |
| `import-linter` | >=2.1 | Architectural layer enforcement via `.importlinter` contract |
| `pytest` | >=8.0 | Test runner for harness regression and non-relaxation tests |
| `uv` | current | Package and environment manager; all commands via `uv run` |

### Integration Notes

- The verify command runs all tools in sequence: `isort → black → ruff → lint-imports → mypy → pytest → detect-secrets → pip-audit → bandit`. This sequence is documented in `AGENTS.md` and in the `Makefile` `verify` target.
- `bandit` is a **code quality** tool (catches security anti-patterns in source code), not a security scanning tool. `detect-secrets` and `pip-audit` are the security scanners.
- `pre-commit` is listed as a dev dependency in `pyproject.toml`. The `.pre-commit-config.yaml` hooks cover secrets detection, whitespace, YAML/TOML check, isort, black, and ruff at minimum.
- `import-linter` enforces the 16-layer architectural contract from tech stack §3.3. A violation fails the verify command.


---

## 2. Inputs, Outputs, and Boundaries

### Required Inputs

Phase H0 has no upstream phase dependencies. It runs before Phase 0 and in parallel with all later phases. The only inputs are:

- A git repository (can be empty or contain only the architecture and plan documents).
- A decision on the package name (needed to populate manifests; can be a placeholder).
- A decision on the initial CI provider (GitHub Actions is assumed; adapt if different).

### Phase Outputs

Phase H0 should produce:

- **Manifests**: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`, `.agent/plan.md` template.
- **Skill templates**: `SKILL.md` templates for test-first repair, safe refactor, dependency update, SAST repair, evaluation, and release.
- **Harness Condition Sheet template**: a structured document that every eval run and release report must populate.
- **AI-readiness rubric**: five-axis rubric with thresholds for S0→S1, S1→S2, S2→S3, and stable S3 progression.
- **Harness drift classifier specification**: `missing`, `stale`, `relaxed`, `out-of-stage`, `clean`.
- **Verify-before-commit command set**: local shell script or `Makefile` target that runs the required checks.
- **Tool and permission model**: documented tool categories, deny-first modes, path allowlists, and network policy.
- **Live telemetry contract**: event types and required fields for session traces.
- **Product run-record contract**: required fields for run records and run events.
- **Operational review template**: structured template for reviewing a completed run.
- **Incident record template**: structured template for recording and closing incidents.
- **Supply-chain and provenance ledger spec**: lockfiles, tool-inventory policy, and hash/signature metadata policy.
- **Manifest/tool-description regression test skeleton**: categorized test cases, not yet executed.
- **Initial harness stage assessment**: a recorded `S0`/`S1`/`S2`/`S3` stage for the repository with next-stage controls listed.
- **Initial AI-readiness report**: a five-axis readiness score snapshot for the repository.

### Non-Goals

Do not implement these in Phase H0:

- Python package scaffold (Phase 0).
- Graph schemas, Python models, or typed evidence (Phase 1).
- Storage backends or repository registry (Phase 2).
- MCP server or task handling (Phase 4).
- Product runtime tools such as `record_run_event`, `evaluate_tool_policy`, or `compute_readiness_score` (Phase 4A).
- Any LLM calls, embeddings, or patch generation.
- Evaluation benchmark runners.
- Full operational review or readiness audit workflows.

Phase H0 defines the contracts and templates those later features use; the runtime implementations follow in later phases.

---

## 3. Role In The Development Contract

Phase H0 is also the operating contract for local AI agents that build the package. The controls defined here apply to the development process itself, not only to the final product.

### 3.1 Hard Constraints (HC1–HC6)

The following hard constraints must be inlined in `AGENTS.md` and inherited by all runtime overlays without relaxation:

| Constraint | Rule |
|---|---|
| HC1 - No plaintext secrets | No secrets in repo files, prompts, logs, or commits. Secret-safe `.gitignore` and pre-commit secret scan required. |
| HC2 - No writes outside path allowlist | No agent-authored writes outside the repo/path allowlist. Out-of-scope writes must be denied and recorded. |
| HC3 - Explicit approval for destructive commands | Destructive commands (force-push, drop table, `rm -rf`, migration without rollback) require explicit human approval before execution. |
| HC4 - No agent-executed irreversible migrations | Database migrations, schema drops, and irreversible infrastructure changes must not be executed autonomously. |
| HC5 - Deny-by-default network egress | No network calls outside the explicitly allowed list. Deny-by-default; allow only documented external services. |
| HC6 - No red-class data in prompts or logs | No PII, credentials, secrets, or red-class data in prompts, tool arguments, trace logs, or stored artefacts. |

Runtime overlays (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`) may specialize but must never relax HC1–HC6.

### 3.2 Session Workflow Contract

For non-trivial work, an agent operating in this repository should:

1. Read the current `AGENTS.md` and applicable `SKILL.md`.
2. Record a `.agent/plan.md` covering scope, commands, expected outputs, and risks.
3. Read current evidence (tests, graph, CI state) rather than relying only on prior session memory.
4. Edit only within the declared scope.
5. Run the verify path before claiming work is done.
6. Record verification results in the plan or a linked run-record event.
7. Summarize remaining risk and uncertainty in the closing summary.

### 3.3 Permission Ladder

| Mode | When to use |
|---|---|
| `plan/read-only` | Ambiguous tasks, security-sensitive tasks, any task where scope is unclear |
| `scoped edit` | After scope and commands are confirmed by plan |
| `scoped execute` | After test and verify commands are known and path-scoped |
| `review/commit` | After deterministic gates pass and no out-of-scope changes are present |

Never use broad bypass modes for CI, releases, or shared repositories.

---

## 4. Manifests And Control-Plane Files

### 4.1 AGENTS.md

`AGENTS.md` is the primary governance manifest for the repository. It must be the single authoritative source for:

- HC1–HC6 hard constraints (inlined, not referenced).
- Success definition and quality gate.
- Assessment rubric (how an agent knows it has done a good job).
- Scope boundary (what directories, files, and external systems an agent may touch).
- Data policy (data classes, retention, redaction rules).
- Cost policy (context budget, token budget, retry limit, wall-clock limit).
- Verify-before-commit gate list.
- Enforcement hooks (pre-commit, CI gates).
- Tool categories and permission modes.
- Memory governance rules.
- Reviewed lesson promotion policy.

`AGENTS.md` must include a non-relaxation declaration: any runtime overlay that contradicts `AGENTS.md` on HC1–HC6 or any quality gate is invalid and must be rejected by drift checking.

Recommended minimum sections in `AGENTS.md`:

```text
## Hard Constraints
## Success Definition
## Scope Boundary
## Data Policy
## Quality Gate
## Cost Policy
## Tool Categories And Permissions
## Verify-Before-Commit
## Memory Governance
## Lesson Promotion Policy
```

### 4.2 Runtime Overlays

Runtime overlays provide agent-specific adjustments without relaxing `AGENTS.md`. Each overlay should begin with an `@AGENTS.md` import declaration or equivalent statement of precedence.

| File | Runtime | Content |
|---|---|---|
| `CLAUDE.md` | Claude Code | `@AGENTS.md` import; Claude-specific tool hints; preferred verify command syntax |
| `.github/copilot-instructions.md` | GitHub Copilot | Copilot-specific scope hints; reference to `AGENTS.md` constraints |
| `.codex/INSTRUCTIONS.md` | Codex CLI | Codex-specific path and command notes; reference to `AGENTS.md` constraints |

Rules:

- Runtime overlays are optional. Create them only when runtime-specific behaviour is needed.
- No runtime overlay may remove, loosen, or override a hard constraint from `AGENTS.md`.
- Drift checking must detect and report any runtime overlay that conflicts with `AGENTS.md`.

### 4.3 .agent/plan.md Template

The `.agent/plan.md` template is the per-session contract. A new session should copy the template and fill in the required fields before beginning non-trivial work.

Recommended template structure:

```text
# Session Plan

## Date And Session ID
## Objective
## Scope
  - Allowed paths:
  - Allowed commands:
  - Out-of-scope:
## Inputs Consulted
## Expected Outputs
## Verify Path
## Risks And Uncertainties
## Residual Risk After Completion
## Linked Run Record (fill when session trace exists)
```

### 4.4 SKILL.md Templates

Create `SKILL.md` templates for the following workflows. Each template should describe the preconditions, steps, verify gate, and completion criteria for that workflow.

| Skill | Purpose |
|---|---|
| `test-first-repair` | Fix a bug by writing a failing test before modifying production code |
| `safe-refactor` | Restructure code without changing observable behaviour |
| `dependency-update` | Update a dependency with lockfile, test, SAST, and licence checks |
| `sast-repair` | Repair a SAST alert with static analysis re-run verification |
| `evaluation` | Run a benchmark or regression suite and record Harness Condition Sheet |
| `release` | Prepare and gate a package release with T1–T4 eval, readiness, and incident checks |

Skill templates live at `.agent/skills/` or an equivalent location documented in `AGENTS.md`.

---

## 5. Stage-Aware Maturity Model

The repository must be assessed against a four-stage maturity model. The assessment is recorded in a harness-stage file and updated whenever the harness changes.

### 5.1 Stage Definitions

**S0 - Greenfield:**
- Branch discipline with protected main branch.
- Baseline manifests (`AGENTS.md`, at least one runtime overlay).
- `.agent/plan.md` template.
- Sandbox or devcontainer note.
- Secret-safe `.gitignore`.
- Pre-commit configuration with at least a secrets scan.
- AI-readiness score ≥ 5 total and ≥ 1 per axis.

**S1 - Walking Skeleton:**
- Tests and lint running in CI.
- Command allowlist documented in `AGENTS.md`.
- Session logging (even file-based JSONL) enabled.
- Governance workflow for merging harness changes.
- AI-readiness score ≥ 12 total and ≥ 2 per axis.

**S2 - Growing:**
- Tool DAG documented and partially enforced.
- Manifest regression suite in CI.
- Schema-grounded memory controls defined.
- SAST, dependency, and licence scans in CI.
- Maintainability gate defined.
- Readiness score computed in CI.
- AI-readiness score ≥ 18 total and ≥ 3 per axis.

**S3 - Production:**
- Held-out evaluation fixtures.
- Adversarial sweep examples.
- Provenance ledger for skills, MCP/prompt assets, and dependencies.
- Incident runbook.
- Governed harness evolution procedure.
- AI-readiness score ≥ 22 total and ≥ 4 per axis.

### 5.2 Monotonic Upgrade Rule

A later stage can add or specialize controls but cannot remove or weaken lower-stage controls. A harness change that would remove a lower-stage control requires an explicit reviewed waiver before it can be accepted.

### 5.3 Stage Assessment Record

The stage assessment record is a small structured file (JSON or YAML) that records:

```text
assessed_ts: ISO-8601 timestamp
stage: S0 | S1 | S2 | S3
readiness_score:
  agent_config: 0-5
  documentation: 0-5
  cicd: 0-5
  code_structure: 0-5
  security: 0-5
  total: 0-25
missing_controls:
  - description of each missing lower-stage control
next_stage_controls:
  - description of each control needed to advance
assessed_by: human | tool
review_due_ts: ISO-8601 timestamp
```

---

## 6. Tool And Permission Model

### 6.1 Tool Categories

| Category | Examples | Default Mode |
|---|---|---|
| `read` | File read, symbol lookup, repo query | Allowed in all modes |
| `search` | Grep, glob, semantic search | Allowed in all modes |
| `edit` | File edit, schema change, test creation | Requires `scoped-edit` mode or explicit path scope |
| `execute` | Shell commands, test runner, formatter, linter, SAST tool | Requires `scoped-execute` mode and command allowlist |
| `review` | Patch review, diff analysis, gate evaluation | Allowed in `review/commit` mode |
| `commit` | Git commit, PR creation, tag | Requires explicit human approval or `review/commit` mode with passing gates |

### 6.2 Permission Modes

| Mode | Allowed categories | Notes |
|---|---|---|
| `read-only` | `read`, `search` | Default for ambiguous or security-sensitive tasks |
| `plan` | `read`, `search`, plus `.agent/plan.md` write | For session planning only |
| `scoped-edit` | `read`, `search`, `edit` within path scope | Path scope must be declared in plan |
| `scoped-execute` | `read`, `search`, `edit`, `execute` within allowlist | Command allowlist from `AGENTS.md` |
| `review-commit` | All categories | Only after all deterministic gates pass |

### 6.3 Path Allowlist Policy

The path allowlist specifies which directories and files an agent may write to or execute in. It should be declared in `AGENTS.md` and checked before any write or execute action. Writes outside the allowlist must be denied and recorded as policy violations.

Default allowlist for this project:

```text
src/
tests/
schemas/
docs/
.agent/
AGENTS.md
CLAUDE.md
pyproject.toml
tox.ini
Makefile
```

Files and directories excluded from the allowlist by default:

```text
.git/
.env
*.key
*.pem
credentials/
secrets/
```

### 6.4 Network Policy

- Default: deny all outbound network connections from agent-executed code.
- Allowed exceptions must be documented in `AGENTS.md` with justification.
- CI-triggered network access (package registries, test data) is permitted when explicitly listed.
- MCP server calls to external services require explicit allow entries.

---

## 7. Live Telemetry Contract

Session telemetry must be live — emitted while the session runs, not reconstructed after failure. A file-based JSONL writer is sufficient in Phase H0.

### 7.1 Required Event Types

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
| `verification_event` | A verify step completes |
| `human_approval` | A human approves an action |
| `human_rejection` | A human rejects an action |
| `policy_decision` | A policy allow/deny/approval-required decision is made |
| `budget_warning` | A soft budget threshold is crossed |
| `budget_hard_stop` | A hard budget threshold is crossed |

### 7.2 Required Fields Per Event

Every event must carry:

```text
event_id: string (non-empty, unique within session)
session_id: string
seq: integer (monotonically increasing within session)
ts: ISO-8601 UTC timestamp
type: one of the event types above
actor: human | agent | tool | system
stage: planning | investigation | editing | execution | verification | review | commit | unknown
redaction_status: not_required | redacted | hash_only | blocked | unknown
```

Tool-call and tool-result events additionally require:

```text
tool_name: string
tool_category: read | search | edit | execute | review | commit
policy_action: allow | deny | approval_required | blocked | not_applicable
input_ref: artefact ID or null
output_ref: artefact ID or null
token_count: integer or null
wall_ms: integer or null
```

Verification events additionally require:

```text
check_name: string
outcome: pass | fail | skip | unknown
artefact_ids: list of artefact IDs
```

### 7.3 Telemetry Invariants

- Events must be append-only. Existing events must not be modified.
- Sequence numbers must be monotonically increasing within a session.
- A session with no `session_end` event is considered incomplete for operational review purposes.
- A session that produced commits or PRs without a passing `verification_event` is a policy violation.

---

## 8. Product Run-Record Contract

The run-record contract specifies the fields that every product workflow must emit. Phase H0 defines the contract; Phase 4A implements the runtime tools.

### 8.1 Run Record Required Fields

```text
run_id: string (high-entropy, non-guessable)
workflow: string (e.g. bug-resolve, patch-review, implementation-check)
user_intent_hash: string (hash of the user-provided issue or request)
repos: list of repo IDs
start_ts: ISO-8601 UTC
end_ts: ISO-8601 UTC or null
status: running | complete | failed | incomplete | unknown | budget-exhausted
model_backend: string
toolset_hash: string (hash of active MCP tools and versions)
policy_id: string
permission_profile: string
context_budget: integer (tokens) or null
run_event_count: integer
harness_condition_id: string or null
final_verdict_id: string or null
incident_ids: list of incident IDs
redaction_policy: string
```

### 8.2 Run Event Required Fields

```text
event_id: string
run_id: string
seq: integer (monotonically increasing within run)
ts: ISO-8601 UTC
type: string (tool_call | gate | context | budget | compaction | approval | denial | monitor | review | incident | promotion)
actor: string
stage: string
input_ref: artefact ID or null
output_ref: artefact ID or null
policy_action: allow | deny | approval_required | blocked | checkpoint | force_unknown | not_applicable
token_count: integer or null
wall_ms: integer or null
artefact_ids: list of artefact IDs
redaction_status: not_required | redacted | hash_only | blocked | unknown
```

### 8.3 Run-Record Invariants

- Run events are append-only and sequence-numbered.
- A run with status `complete` must have a `harness_condition_id` and a `final_verdict_id`.
- A run with status `budget-exhausted` must have the last event be a `budget_hard_stop`.
- A run without a `session_end` or `verification_event` covering the declared verify path is `incomplete`.
- Incidents and promotion candidates must reference source `run_id` and `event_id`.

---

## 9. Verify-Before-Commit Command Set

The local verify command runs before any commit or PR is considered complete. It must be documented in `AGENTS.md` and runnable with a single command.

### 9.1 Required Checks In Order

See `llm-sca-tooling-tech-stack.md` for the authoritative tool list. The verify sequence uses the confirmed stack:

| Step | Command | Failure action |
|---|---|---|
| Import sort | `uv run isort --check .` | Fail; run `uv run isort .` to fix |
| Code format | `uv run black --check .` | Fail; run `uv run black .` to fix |
| Lint | `uv run ruff check .` | Fail; review and fix |
| Import architecture | `uv run lint-imports` | Fail; fix layer violation |
| Type check | `uv run mypy src/` | Fail; fix type errors |
| Unit tests | `uv run pytest tests/unit/ -x` | Fail; do not commit |
| Secrets scan | `detect-secrets scan --baseline .secrets.baseline` | Fail; remove secrets before commit |
| Dependency audit | `uv run pip-audit` | Warn for known; fail for critical CVEs |
| SAST scan | `uv run bandit -r src/ -c pyproject.toml` | Warn for medium; fail for high/critical |
| Domain invariant hooks | Project-defined hooks | Fail when present and failing |
| Manifest non-relaxation | Python check against `AGENTS.md` | Fail if HC1–HC6 are weakened |

### 9.2 Verify Command

Document the canonical verify command in `AGENTS.md`:

```text
verify:
  command: make verify
  equivalent: |
    uv run isort --check . &&
    uv run black --check . &&
    uv run ruff check . &&
    uv run lint-imports &&
    uv run mypy src/ &&
    uv run pytest tests/unit/ -x &&
    detect-secrets scan --baseline .secrets.baseline &&
    uv run pip-audit &&
    uv run bandit -r src/ -c pyproject.toml
  must_pass_before: commit, PR creation, release gate
```

The `make verify` target must be idempotent. Running it twice on an unchanged codebase must produce the same result.

### 9.3 Pre-Commit Configuration

Create a `.pre-commit-config.yaml` that covers at minimum:

- Secret detection (e.g. `detect-secrets`).
- Trailing whitespace and end-of-file fix.
- Import sort check.
- Black format check.
- Ruff lint check.

Additional hooks for SAST, type check, and dependency scan can be added as the harness matures.

---

## 10. Harness Condition Sheet Template

Every evaluation run and release report must include a completed Harness Condition Sheet. Phase H0 defines the template; later phases populate it.

### 10.1 Required Fields

```text
Harness Condition Sheet

Run ID: <run_id>
Report date: <ISO-8601 date>
Phase/milestone: <phase name or milestone label>

## Runtime And Model
- Runtime name and version:
- Model backend and version:
- MCP server version:

## Manifest State
- AGENTS.md revision (git SHA or hash):
- Active runtime overlays and revisions:
- SKILL.md templates active:

## Exposed Tools
- Tool set hash:
- Tools active for this run:
- Tools disabled or not available:

## Permission Mode
- Permission profile:
- Path allowlist (summary or reference):
- Network policy:
- Sandbox or devcontainer:

## Verification Gates
- Verify command used:
- Gates enabled:
- Gates disabled (with justification):

## Context And Cost Policy
- Context budget (tokens):
- Token budget:
- Retry budget:
- Wall-clock budget:
- Compaction policy:

## Telemetry
- Session trace location:
- Trace completeness (complete | incomplete | missing):
- Redaction policy applied:

## Evaluation Notes
- Known limitations:
- Deviations from standard harness:
- Waived controls (with reviewed justification):
```

### 10.2 Harness Condition Sheet Invariants

- A run claiming a positive verdict cannot have `trace completeness: missing`.
- A run with any waived control must have a reviewed justification with owner and expiry date.
- Two runs can only be compared fairly if their Harness Condition Sheets have matching runtime, model, manifest revision, and permission mode.

---

## 11. AI-Readiness Score Model

### 11.1 Five Axes

| Axis | What it measures | Max score |
|---|---|---|
| `agent_config` | Quality of `AGENTS.md`, runtime overlays, plan template, skill templates, and tool/permission model | 5 |
| `documentation` | Architecture docs, quickstart, constraint explanations, limitation notes | 5 |
| `cicd` | CI pipeline coverage (lint, tests, secrets, SAST, dependency, manifest regression), release automation | 5 |
| `code_structure` | Typed models, schema exports, modularity, test coverage, no unsafe patterns | 5 |
| `security` | Secret scanning, SAST, dependency audit, path/network policy, redaction | 5 |
| **Total** | | **25** |

### 11.2 Stage Gate Thresholds

| Transition | Minimum total | Minimum per axis |
|---|---|---|
| S0 → S1 | 5 | 1 |
| S1 → S2 | 12 | 2 |
| S2 → S3 | 18 | 3 |
| Stable S3 | 22 | 4 |

### 11.3 No-Regression Rule

A harness change fails the readiness no-regression check unless either:

- No per-axis readiness score decreases, OR
- The decrease is tied to an explicit reviewed waiver recording the reason, owner, and review-due date.

An AI-readiness report must be comparable over time. It must include the previous report reference and a per-axis delta.

---

## 12. Harness Drift Classifier

### 12.1 Drift Classes

| Class | Meaning | Default response |
|---|---|---|
| `missing` | A required artefact for the current stage does not exist | Warn; block higher-autonomy work until resolved |
| `stale` | A required artefact exists but is outdated relative to its dependencies | Warn; treat as lower confidence |
| `relaxed` | A manifest, policy, or gate has been weakened relative to `AGENTS.md` or a lower stage | Block release and higher-autonomy work until reviewed |
| `out-of-stage` | A control is claimed but inconsistent with the assessed stage | Warn; include in readiness report |
| `clean` | No drift detected for this artefact | No action |

### 12.2 Artefacts Subject To Drift Checking

- `AGENTS.md`
- All runtime overlays
- All `SKILL.md` templates
- Tool descriptions (MCP and CLI)
- CI workflow files
- Pre-commit configuration
- Harness stage assessment record
- AI-readiness report

### 12.3 Relaxation Detection Rules

A drift of class `relaxed` must be reported when:

- An HC1–HC6 constraint in `AGENTS.md` has been weakened or removed.
- A verify-before-commit check that was previously required has been disabled without a reviewed waiver.
- A path allowlist has been broadened beyond its previous scope without review.
- A network deny rule has been removed.
- A SAST, dependency, or secrets-scan gate has been disabled.
- A stage-gating readiness threshold has been lowered.

---

## 13. Supply-Chain And Provenance Ledger

### 13.1 What Must Be Recorded

For each tool, runtime, or prompt asset used in product workflows, record:

```text
component_type: runtime | mcp_server | language_backend | analyser | prompt_asset | skill | dependency
name: string
version: string
install_source: package_registry | git_url | local_path
hash_or_digest: string or null
signature_verified: boolean or null
last_updated_ts: ISO-8601
dependency_scan_ts: ISO-8601 or null
dependency_scan_outcome: pass | warn | fail | not_run
notes: string or null
```

### 13.2 Policy

- All dependencies used in workflows must appear in a lockfile (`uv.lock`, `requirements.txt`, or equivalent).
- MCP server versions must be pinned or hash-verified.
- Prompt asset and skill versions must be tracked (git SHA or content hash).
- A change to the lockfile or any tool-manifest file triggers a dependency scan in CI.
- Analyser versions (Bandit, Semgrep, CodeQL, etc.) are recorded in the Harness Condition Sheet for every SARIF-producing run.

### 13.3 Prompt And Document Injection Canaries

Before trusting text from external sources (repository content, tool output, issue text), apply prompt-injection canary checks. Canaries are not a complete defence, but they are a required baseline:

- Look for instruction-format text in repository files, issue descriptions, and tool output.
- Flag any suspicious token sequences that resemble system-prompt injection attempts.
- Record detection events in the session trace.

---

## 14. Manifest And Tool-Description Regression Test Skeleton

Phase H0 creates the test skeleton. Phase 4 and later phases add concrete test cases.

### 14.1 Required Test Categories

| Category | What it tests |
|---|---|
| `visible_behaviour` | Tool calls produce expected outputs for standard inputs |
| `hidden_policy` | Tool calls are denied, warned, or flagged for policy-sensitive inputs |
| `tool_order` | Tool call ordering does not change outcomes in order-dependent cases |
| `semantic_mutation` | A semantically equivalent change to a manifest or prompt does not change outputs for tested inputs |
| `spec_evolution` | Adding a new field or enum value to a schema does not break existing consumers |
| `non_relaxation` | A runtime overlay that weakens HC1–HC6 or a gate is rejected |

### 14.2 Skeleton Files

Create placeholder test files at:

```text
tests/
  harness/
    test_manifest_regression.py    # visible_behaviour, hidden_policy, tool_order
    test_semantic_mutation.py      # semantic_mutation, spec_evolution
    test_non_relaxation.py         # non_relaxation checks for AGENTS.md and overlays
```

Each file should contain at least one commented-out stub test case documenting what the real test should check. The stubs are not executed in Phase H0; they serve as specification.

---

## 15. Incident Record Template

Every P0 or P1 operational failure must produce an incident record. Phase H0 defines the template.

```text
# Incident Record

## Incident ID
## Date Opened
## Severity: P0 | P1 | P2 | P3

## Impact
- Systems/workflows affected:
- User or data scope:
- Estimated duration:

## Timeline
- Detection time:
- Containment time:
- Remediation time:
- Incident closed:

## Root Cause
- Proximate cause:
- Contributing factors:
- Evidence links (run_id, event_id, artefact_id):

## Containment
- Immediate action taken:
- Blast radius bounded by:

## Remediation
- Fix applied:
- Verification that fix is effective:
- Rollback path if fix fails:

## Follow-Up
- Detector or eval regression created: Yes | No | N/A
- Static-analysis rule created: Yes | No | N/A
- Memory or policy update: Yes | No | N/A
- Readiness task added: Yes | No | N/A

## Reviewer Closure
- Reviewer:
- Closed date:
- Residual risk accepted:
```

P0 and P1 incidents require all follow-up fields to be filled before the incident is closed.

---

## 16. Operational Review Template

The operational review template is used after any significant workflow run to assess trace completeness, policy compliance, budget behaviour, and improvement candidates.

```text
# Operational Review

## Run ID
## Review Date
## Reviewer

## Trace Completeness
- session_start present: Yes | No
- session_end present: Yes | No
- All tool calls logged: Yes | No | Partial
- All verification events logged: Yes | No | Partial
- Redaction correctly applied: Yes | No | Unknown
- Overall: complete | incomplete | missing

## Policy Compliance
- All tool calls within permission mode: Yes | No
- All writes within path allowlist: Yes | No
- No HC1–HC6 violations: Yes | No
- Policy violations recorded: (count and description)
- Overall: compliant | noncompliant

## Budget Behaviour
- Token budget used: (amount / limit)
- Retry budget used: (amount / limit)
- Wall-clock budget used: (amount / limit)
- Budget hard stops triggered: Yes | No
- Compaction events: (count)
- Overall: within-budget | soft-warning | hard-stop

## Anomalies
- Repeated identical tool calls: Yes | No
- Repeated failing gate: Yes | No
- Context growth without new evidence: Yes | No
- Denied-operation storm: Yes | No
- Stale or mixed snapshot evidence used: Yes | No
- Out-of-scope write attempted: Yes | No
- Missing required verification: Yes | No
- (Additional anomalies detected):

## Gate Adequacy
- Required gates ran: Yes | No | Partial
- Gate results: (pass/fail/skip per gate)
- Missing gates: (list)

## Incidents
- Incidents opened: (count and IDs)
- Open incidents unresolved: Yes | No

## Promotion Candidates
- Improvement candidates identified: (count and short descriptions)
- Reviewed before promotion: Yes | No

## Overall Verdict
- process-compliant | process-noncompliant | trace-incomplete | budget-exhausted | needs-readiness-work
```

---

## 17. Exit Criteria

### Source Plan Exit Criterion

Every implementation phase can declare its Harness Condition Sheet.

**Concrete H0 acceptance:**

- The Harness Condition Sheet template exists and is documented.
- At least one filled-in Harness Condition Sheet exists for the Phase H0 implementation run itself.

---

### Source Plan Exit Criterion

Every workflow-producing phase has a session trace and verification record.

**Concrete H0 acceptance:**

- The session telemetry contract is documented with event types and required fields.
- A file-based JSONL writer skeleton exists and can emit at least `session_start` and `session_end`.

---

### Source Plan Exit Criterion

A parseable run-record schema exists before workflow implementation begins, even if the first writer is file-based.

**Concrete H0 acceptance:**

- The run-record and run-event required fields are documented in this plan.
- A placeholder schema file (`run-record.schema.json`) or equivalent stub exists in the repository.

---

### Source Plan Exit Criterion

A local verify path exists and is documented.

**Concrete H0 acceptance:**

- `make verify` (or equivalent) exists and is runnable.
- The verify command is documented in `AGENTS.md`.
- Running the verify command on an unmodified checkout completes without error.

---

### Source Plan Exit Criterion

Manifest and tool-description changes have tests or documented review criteria.

**Concrete H0 acceptance:**

- The manifest regression test skeleton exists with stub test cases in the correct categories.
- Review criteria for manifest changes are documented in `AGENTS.md`.

---

### Source Plan Exit Criterion

Operational review and incident templates are available for failed runs.

**Concrete H0 acceptance:**

- The operational review template exists as a file.
- The incident record template exists as a file.
- Both templates are referenced in `AGENTS.md`.

---

### Source Plan Exit Criterion

The current repository has an assessed harness stage, readiness score, and explicit next-stage controls.

**Concrete H0 acceptance:**

- A harness-stage assessment record file exists.
- The record includes a stage (`S0`–`S3`), a per-axis readiness score, missing controls, and next-stage controls.
- The record was produced after Phase H0 artefacts were created.

---

### Source Plan Exit Criterion

Harness drift checks reject relaxed policy changes.

**Concrete H0 acceptance:**

- The `test_non_relaxation.py` stub includes at least one case that would fail if HC1–HC6 were weakened.
- The drift classifier definitions are documented with `relaxed` detection rules.
- At least one CI step (pre-commit or workflow) checks for secrets-scan bypass or HC1–HC6 removal.

---

### Source Plan Exit Criterion

AI-readiness reports are comparable over time and fail the release gate when a readiness axis regresses without an accepted waiver.

**Concrete H0 acceptance:**

- The five-axis rubric is documented with per-axis scoring criteria.
- The no-regression rule is documented.
- An initial AI-readiness report exists for the repository.

---

### Source Plan Exit Criterion

Feature readiness is not accepted from a demo run without telemetry, verification, and evaluation artefacts.

**Concrete H0 acceptance:**

- `AGENTS.md` explicitly states that feature acceptance requires a Harness Condition Sheet, session trace, and passing verify path.
- The local-agent development contract in §3 of this document is referenced in `AGENTS.md`.

---

## 18. Definition Of Done

Phase H0 is done when:

- `AGENTS.md` exists with inlined HC1–HC6, success definition, scope boundary, data policy, quality gate, cost policy, tool categories, verify-before-commit list, memory governance, and lesson promotion policy.
- At least one runtime overlay exists and declares `AGENTS.md` precedence.
- `.agent/plan.md` template exists.
- `SKILL.md` templates exist for the six listed workflows.
- Harness Condition Sheet template exists and is documented.
- Verify-before-commit command set is documented and runnable.
- Pre-commit configuration is active with at minimum secrets detection.
- Session telemetry contract is documented with event types and required fields.
- Run-record and run-event required fields are documented.
- AI-readiness rubric with five axes and stage thresholds is documented.
- Harness drift classifier definitions are documented.
- Supply-chain and provenance ledger policy is documented.
- Manifest regression test skeleton exists with stub test cases.
- Incident record template exists.
- Operational review template exists.
- Harness-stage assessment record exists for the repository.
- Initial AI-readiness report exists for the repository.
- All templates and manifests are referenced in `AGENTS.md`.

---

## 19. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Phase H0 is deferred until features exist | Feature work is unauditable; telemetry, calibration, and evaluation are unreliable | Start H0 before Phase 0; require Harness Condition Sheet for every phase acceptance |
| Manifests are created but ignored during development | Hard constraints are violated silently | Enforce pre-commit hook for non-relaxation check; make CI fail on HC1–HC6 drift |
| Runtime overlays contradict AGENTS.md | Agents behave differently depending on which overlay is active | Drift checker; CLAUDE.md must import @AGENTS.md and be tested for non-relaxation |
| Session traces are incomplete or missing | Operational review cannot reconstruct causality | Require session_start/end and verification events for phase acceptance; block incomplete runs from claiming verdicts |
| AI-readiness score becomes a checkbox exercise | Scores increase without real capability improvement | Tie scores to concrete artefact existence and CI outcomes, not self-assessment |
| Harness drift classifier is too strict | Legitimate changes are blocked unnecessarily | Allow reviewed waivers; distinguish `relaxed` (blocks release) from `stale` (warns only) |
| Supply-chain ledger is not updated when tools change | Unknown tool versions in Harness Condition Sheets | Include tool-version recording in the verify path and CI workflow |
| Incident template exists but incidents are never opened | Failures are hidden in prose summaries | Reference incident template in AGENTS.md; require incident link for P0/P1 outcomes in operational review |

---

## 20. Phase H0 Completion Report Template

When Phase H0 implementation is complete, report:

```text
Phase H0 completion report

Implemented artefacts:
- AGENTS.md (revision):
- Runtime overlays:
- .agent/plan.md template:
- SKILL.md templates:
- Harness Condition Sheet template:
- Verify command:
- Pre-commit config:
- Session telemetry contract location:
- Run-record contract location:
- AI-readiness rubric location:
- Harness drift classifier doc location:
- Manifest regression test skeleton:
- Incident template location:
- Operational review template location:
- Harness stage assessment record:
- Initial AI-readiness report:

Verification:
- Verify command runs clean: Yes | No
- Pre-commit hooks active: Yes | No
- Non-relaxation stub tests present: Yes | No
- Harness Condition Sheet filled for this run: Yes | No

Exit criteria:
- Harness Condition Sheet template exists and is documented:
- Session telemetry contract documented:
- Run-record contract documented:
- Local verify path documented and runnable:
- Manifest regression test skeleton with stubs:
- Operational review and incident templates:
- Harness stage assessed:
- AI-readiness report produced:
- HC1–HC6 non-relaxation check in CI:
- Initial readiness report exists and is comparable:
- AGENTS.md references feature acceptance criteria:

Known limitations:
-

Follow-up for Phase 0:
-
```

---

## 21. Minimal First Slice Within Phase H0

If Phase H0 needs to be split further, implement this first:

1. Create `AGENTS.md` with inlined HC1–HC6, scope boundary, and verify-before-commit list.
2. Create `CLAUDE.md` with `@AGENTS.md` import.
3. Create `.agent/plan.md` template.
4. Create `.pre-commit-config.yaml` with secrets detection and formatting checks.
5. Document the verify command (`make verify` or equivalent).
6. Create the Harness Condition Sheet template file.
7. Run the harness-stage assessment and record the result.
8. Produce the initial AI-readiness report.

The remaining artefacts (SKILL.md templates, operational review template, incident template, manifest regression stubs, supply-chain ledger policy) can follow in a second slice.
