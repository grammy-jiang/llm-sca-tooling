# Plan 06 — Fix the three MCP-server meta-findings

> **Date**: 2026-05-19
> **Author**: audit skill self-review (run_id `impl-check:ic:7124d6632adc4d84a5d08804611df089`)
> **Scope**: source code fixes in `src/llm_sca_tooling/mcp_server/` only. The companion 14 audit-skill issues (S1-S14) were applied in place to `~/.claude/skills/audit/SKILL.md` and `~/.claude/skills/audit/references/mcp-workflow.md`; see "Appendix A — Skill changes (already applied)" at the end of this document for the record.
> **Source artefacts**:
> - `.agent/artifacts/compliance_report_20260519.md` (the audit that surfaced these)
> - `.agent/artifacts/clause_investigation_20260519.json`
> - `src/llm_sca_tooling/mcp_server/tools.py`
> - `src/llm_sca_tooling/fl/models.py`

---

## 1. Executive Summary

During the 2026-05-19 audit of `evidence-sca`, three "meta-findings" were raised against the `llm-sca-tooling` MCP server. On deeper investigation:

| Finding | Status | Truth |
|---|---|---|
| M1 — `task_status` / `task_result` / `task_cancel` schemas omit `task_id` | **Confirmed bug** | Handlers require `task_id`; descriptors at `tools.py:2680-2713` declare no `input_schema`. |
| M2 — `get_relevant_files` returns up to 1.3 MB per call | **Confirmed bug** | One line (`tools.py:432`) unconditionally inlines the full context bundle alongside the already-present `context_bundle_ref`. Violates the architecture's own "Large-resource rule" (`docs/llm-sca-tooling-architecture.md` §2.1). |
| M3 — Score field carries the `derivation` enum instead of a number | **Retracted — operator error** | `combined_score: float ∈ [0, 1]` IS present on every `CandidateFile` (`fl/models.py:63`); the earlier audit's offline extraction script searched for `score` / `rank` / `similarity` and missed `combined_score`. The skill change for S9 documents this; no code change needed. |

The plan has two phases:

1. **Phase B — Server fixes** (M1 + M2): two small code changes; M1 is purely additive, M2 requires a backwards-compat decision.
2. **Phase C — Re-audit**: run the updated audit skill end-to-end to confirm M1 and M2 are closed and the actionable-unknown count drops.

Estimated effort: ~2 hours of focused work including tests, plus ~30 minutes for the re-audit.

---

## 2. Phase B1 — M1: Add `task_id` to task-tool schemas

**File**: `src/llm_sca_tooling/mcp_server/tools.py`

### Symptom

A compliant MCP client cannot poll task status:

```
mcp__llm-sca-tooling__task_status()
→ MCP error -32603: Internal error
```

### Root cause

`tools.py:2680-2713` registers three task tools with no `input_schema=` argument to `_descriptor(...)`:

```python
(_descriptor("task_status", "Poll task status.", read_only=True, ..., tier=2),
 handlers.task_status),
(_descriptor("task_result", "Fetch task result.", read_only=True, ..., tier=2),
 handlers.task_result),
(_descriptor("task_cancel", "Cancel a queued or running task.", ..., tier=2),
 handlers.task_cancel),
```

The default schema produced by `_descriptor` (and `_object_schema({})` at `tools.py:110-118`) is:

```json
{"type": "object", "additionalProperties": false, "properties": {}, "required": []}
```

But the handlers at `tools.py:1402-1424` all require `task_id`:

```python
async def task_status(self, args):
    task = self._tasks.get(_required_str(args, "task_id"))   # ← required at runtime
```

Schema-validating clients (Claude Code / Anthropic SDK) reject any extra args because of `additionalProperties: false`, so `task_id` cannot be passed even though the handler requires it. Result: every call raises `Internal error`.

### Fix

Add the missing `input_schema=` to each of the three descriptors:

```python
# tools.py:2680-2690 — task_status
(
    _descriptor(
        "task_status",
        "Poll task status.",
        read_only=True,
        side_effect_class="none",
        required_mode="read/search",
        input_schema=_object_schema(                       # NEW
            {"task_id": {"type": "string"}},
            ["task_id"],
        ),
        tier=2,
    ),
    handlers.task_status,
),
```

Apply the same `input_schema=` block to:

- `task_result` descriptor at `tools.py:2691-2701`
- `task_cancel` descriptor at `tools.py:2702-2713`

`task_list` at `tools.py:2714-2724` legitimately takes no args — leave it. (Its "Internal error" when called is governed by `config.task_listing_allowed` returning `False` by default; that's a config story, not a schema bug. If discoverability of running tasks is desired in single-user mode, enable `enable_task_list=True` in `McpServerConfig`.)

### Tests

Add `tests/unit/mcp_server/test_task_tool_schemas.py`:

```python
def test_task_status_schema_requires_task_id():
    descriptors = build_default_tool_descriptors(...)   # whatever existing helper
    schema = next(d for d, _ in descriptors if d.name == "task_status").input_schema
    assert "task_id" in schema["properties"]
    assert schema["required"] == ["task_id"]

def test_task_status_rejects_missing_arg(client):
    with pytest.raises(ToolInvalidArguments):
        client.call_tool("task_status", {})

def test_task_status_returns_for_known_task(client, running_task_id):
    response = client.call_tool("task_status", {"task_id": running_task_id})
    assert response["task"]["task_id"] == running_task_id
```

Mirror the schema test for `task_result` and `task_cancel`.

### Risk

**Low**. Purely additive schema. Any existing internal caller that already passes `task_id` continues to work; clients that previously failed now succeed. No behaviour change in the handler.

### Acceptance

- [ ] `make verify` exits 0.
- [ ] Calling `mcp__llm-sca-tooling__task_status(task_id="<id>")` from a schema-validating MCP client succeeds.
- [ ] Calling `mcp__llm-sca-tooling__task_status()` (without args) returns a clear schema-validation error, not `Internal error`.

---

## 3. Phase B2 — M2: Stop inlining the full context bundle by default

**File**: `src/llm_sca_tooling/mcp_server/tools.py:404-438`

### Symptom

```
mcp__llm-sca-tooling__get_relevant_files(issue_text="…", max_files=5)
→ Error: result (1,034,737 characters) exceeds maximum allowed tokens.
```

Every call inlines the full `ContextBundle`, regardless of caller need.

### Root cause

`tools.py:431-432` always inlines the bundle:

```python
payload = result.model_dump(mode="json")
payload["context_bundle"] = context.model_dump(mode="json")   # ← M2
```

But `LocalisationResult` already carries `context_bundle_ref` (a small URI handle to fetch the bundle on demand). The inline copy is redundant and violates the architecture's own §2.1 "Large-resource rule":

> Bounded work should use `code-intelligence://graph/slice/...` or `get_graph_slice(...)`, because full repo graphs can exceed client context, memory, and transport limits.

The same logic applies to context bundles.

### Fix

Gate inlining behind a new optional argument `include_context_bundle: bool = False`. Update both the handler and the descriptor:

**Handler change** (`tools.py:404-438`):

```python
async def get_relevant_files(self, args: dict[str, Any]) -> ToolResult:
    issue_text = _required_str(args, "issue_text")
    include_context_bundle = bool(args.get("include_context_bundle", False))   # NEW
    # ... (existing call assembly unchanged) ...
    result, context = await get_relevant_files(...)
    payload = result.model_dump(mode="json")
    if include_context_bundle:                                                  # CHANGED
        payload["context_bundle"] = context.model_dump(mode="json")
    return ToolResult(
        tool_name="get_relevant_files",
        status="completed",
        payload=payload,
        diagnostics=[{"message": result.uncertainty}] if result.uncertainty else [],
    )
```

**Descriptor change** (`tools.py:2265-2278`):

```python
input_schema=_object_schema(
    {
        "issue_text": {"type": "string"},
        "repos": {"type": "array"},
        "failing_tests": {"type": "array"},
        "coverage_path": {"type": "string"},
        "max_files": {"type": "integer"},
        "include_symbols": {"type": "boolean"},
        "snapshot": {"type": "string"},
        "use_embedding": {"type": "boolean"},
        "include_context_bundle": {"type": "boolean"},        # NEW
        "budget": {"type": "object"},
    },
    ["issue_text"],
),
```

### Backwards-compatibility decision (NEEDS HUMAN OK)

Default switching from inline-on to inline-off is the *correct* architectural fix, but it IS an API-shape change. Two rollouts to choose from:

| Option | Default | Migration | Risk |
|---|---|---|---|
| **A (recommended)** | `include_context_bundle=False` | Internal callers that pipe `get_relevant_files` output into prompts (workflow launchers like `run_issue_resolution`) explicitly pass `True` in the same commit. Note in `CHANGELOG.md`. | Medium — needs a `grep -n 'context_bundle' src/llm_sca_tooling` sweep before merging. |
| **B (conservative)** | `include_context_bundle=True` | Add a one-cycle deprecation warning when the arg is omitted; switch the default to `False` in the next minor. | Low this cycle; defers the architectural fix one cycle. |

The architecture's "Large-resource rule" makes A the right long-term call; B reduces churn risk for any external callers. The choice belongs to the maintainer of `llm-sca-tooling`.

### Tests

Add `tests/unit/mcp_server/test_get_relevant_files_payload.py`:

```python
def test_default_payload_omits_context_bundle(client, fixture_repo):
    response = client.call_tool("get_relevant_files", {"issue_text": "test"})
    assert "context_bundle" not in response["payload"]
    assert "context_bundle_ref" in response["payload"]
    assert len(json.dumps(response["payload"])) < 50_000

def test_opt_in_payload_includes_context_bundle(client, fixture_repo):
    response = client.call_tool(
        "get_relevant_files",
        {"issue_text": "test", "include_context_bundle": True},
    )
    assert "context_bundle" in response["payload"]
    # equality with prior behaviour
    assert response["payload"]["context_bundle"]["files"][0]["candidate_file"]["file_path"]
```

### Pre-merge sweep (Option A only)

Before merging Option A, audit internal callers that may rely on the inline bundle:

```bash
grep -rn 'context_bundle' src/llm_sca_tooling/ --include="*.py" \
  | grep -v 'context_bundle_ref'
```

Workflow launchers (`run_issue_resolution`, `run_implementation_check`, `run_patch_review`, etc.) that consume `get_relevant_files` output downstream need to explicitly pass `include_context_bundle=True` where they were relying on the inline data. The launcher implementations live in:

- `src/llm_sca_tooling/workflows/` (per-workflow modules)
- `src/llm_sca_tooling/mcp_server/tools.py` (workflow-launcher tool handlers)

### Risk

- **A**: Medium. Behaviour change. Requires the call-site sweep above. The win is auditable, predictable response sizes.
- **B**: Low this cycle. Defers the architectural fix.

### Acceptance

- [ ] `make verify` exits 0.
- [ ] Default `get_relevant_files` call on `evidence-sca` returns < 50 KB.
- [ ] `include_context_bundle=True` returns the prior payload shape.
- [ ] `context_bundle_ref` is present in both modes (callers can still discover the bundle via reference).

---

## 4. Phase B3 — M3: Retraction (no code change)

The earlier audit's claim that "the score field carries the `derivation` enum instead of a number" was **operator error**. The actual response includes BOTH fields:

| Field on each `CandidateFile` (from `src/llm_sca_tooling/fl/models.py:57-67`) | Type | Purpose |
|---|---|---|
| `combined_score` | `float ∈ [0, 1]` | Numeric ranking score |
| `confidence` | `ConfidenceLevel` enum | Derivation tier (`unknown` / `heuristic` / `analyser` / `parser`) |

The audit's offline extraction script looked for keys named `score` / `rank` / `similarity` and missed `combined_score`. Both fields are returned and correct.

### Action

- Skill change S9 (already applied) documents this in `SKILL.md` so future audits don't repeat the confusion.
- Amend `.agent/artifacts/compliance_report_20260519.md` §5 to retract M3 (see end of this plan for the exact patch).

No source-code change.

---

## 5. Sequenced Workplan

```
Phase B — MCP server                              owner: tooling maintainer
  B1. M1 fix (three descriptors).                  ← isolated; safe to ship alone
        - Edit tools.py:2680-2713 to add input_schema={task_id}.
        - Add tests/unit/mcp_server/test_task_tool_schemas.py.
        - make verify → must exit 0.
  B2. M2 decision: Option A or Option B.           ← needs maintainer approval
  B3. M2 fix per chosen option.
        - If A: grep sweep for inline-bundle consumers first.
        - Edit tools.py:404-438 (gate inlining).
        - Edit tools.py:2265-2278 (add include_context_bundle to schema).
        - Update workflow launchers that need the bundle (pass True).
        - Add tests/unit/mcp_server/test_get_relevant_files_payload.py.
        - make verify → must exit 0.
  B4. M3 retraction.
        - Edit .agent/artifacts/compliance_report_20260519.md §5 to mark M3 as retracted.
  B5. Cut a patch release with both fixes and document the API-shape change in CHANGELOG.

Phase C — Re-audit (this repo)                    owner: anyone, using the updated skill
  C1. Re-run audit skill on evidence-sca.
  C2. Confirm:
        - task_status polling works end-to-end (M1 closed).
        - get_relevant_files responses fit token budget (M2 closed).
        - combined_score is correctly reported in clause_investigation.
        - Section-header clauses are listed as "non-actionable" rather than gaps.
        - The unknown-clause count drops materially relative to the 2026-05-19 run.
```

---

## 6. Acceptance Criteria

- [x] **B1**: `mcp__llm-sca-tooling__task_status(task_id="<id>")` now accepts the documented argument; missing-arg call returns a schema-validation error rather than `Internal error`. **Met** — PR #1 merged on 2026-05-19 (commit `882a8c5`).
- [x] **B3 (adjusted)**: `include_context_bundle` argument is plumbed through; default is `True` (preserving prior behaviour because `context_bundle_ref` is not yet a fetchable resource); callers can pass `include_context_bundle=False` to drop the bundle when payload size matters. **Met** — PR #2 merged on 2026-05-19 (final commit `5047f0b`). See Appendix B for the adjustment story.
- [x] **B4**: M3 retraction recorded in the committed, propagating tree — §4 ("Phase B3 — M3: Retraction") of this document is the canonical statement that `combined_score` IS in the response and the original finding was operator error; Appendix B.1 cross-references that retraction in the closure table. The gitignored `.agent/artifacts/compliance_report_20260519.md` is annotated locally for anyone working in this clone, but the propagating record lives here, in plan-06. **Met** by committing this document.
- [ ] **C**: A fresh audit run on `evidence-sca` produces a new `compliance_report_YYYYMMDD.md` with the section-header noise removed and a materially smaller actionable-unknown count. **Pending re-audit on a session started after M1+M2 merged.**

---

## 7. Out of Scope (deliberately deferred)

- The 10 actionable unknowns from the 2026-05-19 audit (e.g. confirming `.agent/templates/harness-condition-sheet.md` exists). These are *implementation-completeness* questions for the product, not audit-tooling questions. Re-running the audit after M1/M2 land is the right first step before manually chasing each one.
- Adding `compute_readiness_score`, `classify_harness_drift`, etc., as first-class MCP tools accessible by name (currently only invocable via the `run_readiness_audit` workflow launcher). Tracked separately under Phase 19 work.
- Changing the `confidence` enum semantics — `parser` / `analyser` / `heuristic` / `unknown` is the architecture's signal-tier classification and is correct; S9 only asks the skill to document it, not to change the values.
- Enabling `task_list` by default — single-user policy decision; leave as opt-in via `McpServerConfig.enable_task_list`.

---

## Appendix A — Skill changes (already applied)

The 14 companion issues in the `audit` skill (S1-S14) were applied in place on 2026-05-19 to:

- `/home/grammy-jiang/.claude/skills/audit/SKILL.md`
- `/home/grammy-jiang/.claude/skills/audit/references/mcp-workflow.md`

Summary of applied changes:

| ID | Change | Location |
|---|---|---|
| S1 | `get_relevant_files` arg `query` → `issue_text` | SKILL.md step 4; references throughout + table |
| S2 | `run_static_analysis` arg `predicate` → `analyser` | SKILL.md patch-review section; references body + table |
| S3 | `get_relevant_files` arg `repo` → `repos` array (optional) | references body + table |
| S4 | Forbidden-actions clarification: Read/grep allowed for **spec assembly**; only per-clause **investigation** is restricted | SKILL.md step 3/4 |
| S5 | Spec assembly guidance for large docs (focused checklist, multi-call splitting) | SKILL.md step 3 |
| S6 | "Start MCP server" softened to "if not already exposed as `mcp__llm-sca-tooling__*`" | SKILL.md top section |
| S7 | Lead with agent-native `mcp__llm-sca-tooling__*` call form; keep JSON-RPC as alternate in references | SKILL.md throughout |
| S8 | Unknown-clauses triage rule: skip pure section headers (no testable predicate) | SKILL.md step 4 and §6 template |
| S9 | Document both `combined_score` (numeric) and `confidence` (enum) fields | SKILL.md step 4; Notes |
| S10 | Note M1 server bug and workaround (rely on `index_status: "partial"`) | SKILL.md step 2; Notes |
| S11 | Warn about ~0.5–1.5 MB response size until M2 lands; suggest `max_files=3-5` or post-process | SKILL.md step 4; Notes |
| S12 | Date-stamped artifact filenames (`*_YYYYMMDD.json`) | SKILL.md steps 3/4/5/6 and Completion Criteria |
| S13 | `make verify` required only for audits that produced source-code changes | SKILL.md Completion Criteria; Verify Gate |
| S14 | `resources/read` not available from Claude Code — cite `run_id` and `session_trace_manifest_ref` instead | SKILL.md §6 template; Completion Criteria |

No further work needed on the skill side until Phase C verifies the updated recipes against the post-fix server.

---

## Appendix B — Closure (added 2026-05-19, post-merge)

Records what actually happened versus the plan above. Original body is preserved unchanged; this appendix accumulates outcomes and lessons.

### B.1 Server-side changes that landed

| Phase | PR | Commits | Net diff |
|---|---|---|---|
| B1 (M1) | `llm-sca-tooling#1` | `882a8c5` | 1 src file (+12), 1 new test file (76 lines) |
| B3 (M2) | `llm-sca-tooling#2` | `6da48bd` → `0682384` → `ad5587f` → `2eb0ecd` → `e7e0a1a` → `5047f0b` | M2 core + Copilot review response + 4 side-quest fixes |
| B4 (M3) | `llm-sca-tooling#3` (this PR) | M3 retraction recorded in §4 of this document plus the row above in this table; gitignored compliance report is annotated locally but does not propagate | docs-only |
| B5 (release) | — | — | deferred; B1+B2 are independently shipping minor patch versions |

### B.2 The M2 Option A → B adjustment

The original plan (§3) presented two options for the `include_context_bundle` default:

- **Option A**: default `False`. Architecturally aligned with the "Large-resource rule"; counts on `context_bundle_ref` being a fetchable resource.
- **Option B**: default `True` (deprecation warning). Conservative; defers the architectural fix.

The MCP-native consumer sweep (§3 "Pre-merge sweep") returned **zero internal callers** of `payload["context_bundle"]`, so Option A initially looked safe. The first M2 commit (`6da48bd`) implemented Option A.

**The Copilot reviewer caught a third concern the plan missed**: `context_bundle_ref` isn't actually a fetchable URI today. `fl/localisation.py:56` sets it to `{"kind": "inline", "file_count": N}` (inline metadata), and no `context-bundle` resource handler is registered. Option A therefore made a false promise — callers following the "default omits the bundle; fetch via the ref" contract would silently lose access to the bundle.

Resolution (commit `0682384`): flip the default to `True` (Option B), but keep the flag as an explicit **opt-out** for callers facing token-budget limits. Same flag surface, opposite default. The proper architectural fix (register a real `context-bundle` resource so Option A becomes honest) is now a tracked follow-up.

**Lesson:** "zero internal consumers" is necessary but not sufficient. Before changing a default, verify the **advertised contract** the new default exposes is actually deliverable. Internal call-site analysis is silent about the obligations the API surface implies to external readers.

### B.3 The grep-vs-graph distinction

The plan body (§3 "Pre-merge sweep") said: *"Run the grep sweep for inline-bundle consumers."* That wording is wrong, and a follow-up question from the maintainer surfaced why: the architecture explicitly says to use the typed graph index, not grep. Skipping the index would be the same anti-pattern the audit skill exists to prevent.

The sweep was therefore re-run with `mcp__llm-sca-tooling__get_relevant_files`. The result: every top-5 ranked match was a `docs/*.md` file — same docs-bias pattern the 2026-05-19 audit already documented. No `src/` file surfaced. A targeted `grep -rn 'context_bundle' src/ tests/` returned 3 hits in total (the one we were fixing + 2 typed-attribute references in `fl/investigate.py` that are unrelated to the MCP JSON payload).

The two retrieval problems are not the same:

| Question | Right tool |
|---|---|
| "Who calls this symbol / depends on this function?" | Graph index — `find_callers`, `get_graph_slice`, dataflow edges. Symbol-level facts. |
| "Where in the source does this dict-key / string literal occur?" | Text search — `grep`. The graph index does not model dict-literal keys as nodes. |

**Lesson:** When updating the audit skill's recipes for future M-style fixes, distinguish the two questions explicitly. Phrasing like "Run a sweep for X" should specify which tool is appropriate to the kind of X. Plan-06 §3 is left as written for fidelity, but the next plan should split the sweep step into "(a) call-graph sweep via the index" and "(b) text-pattern sweep via grep — only for non-symbol queries."

### B.4 Side-quest bugs surfaced during M2 work

These weren't in the plan; they were discovered by exercising the M2 PR through CI and turned out to be real downstream bugs (would have hurt anyone copying the workflow template into their own repo).

| # | Bug | Fix |
|---|---|---|
| SQ-1 | `.github/workflows/llm-sca-tooling.yml` ran `apt-get install -y semgrep`; semgrep ships only as a Python package | PR #2 commit `ad5587f` — install via `uv tool install semgrep` |
| SQ-2 | Same workflow ran `uv add llm-sca-tooling` — adds a package to itself in the home repo, fails for CI that already has the dep in pyproject.toml | PR #2 commit `ad5587f` — switch to `uv sync --frozen` |
| SQ-3 | `llm-sca-tooling harness status` CLI command crashed with `FileNotFoundError` + exit 2 when the optional `local-agent-harness` companion binary was absent. The handler already had a graceful "not available" warning for non-zero exits; the missing-binary path bypassed it | PR #2 commit `2eb0ecd` — catch `FileNotFoundError` explicitly; route to same warning |
| SQ-4 | Same workflow passed `--operational-gate-required` to `release gate`; this flag does not exist in the CLI. Closest semantic match is `--fail-on-any` | PR #2 commit `e7e0a1a` |
| SQ-5 | Architectural: the workflow file was a downstream-consumer **template** sitting in `.github/workflows/`, so GitHub Actions executed it on the home repo where its assumptions don't hold (it tries to install llm-sca-tooling as a dependency, enforce Phase 18 release gate against home-repo state, etc.) | PR #2 commit `5047f0b` — relocated to `.github/workflow-templates/` (GitHub's canonical non-executing template location); header comment now self-documents the location |

**Lesson:** an end-to-end audit infrastructure exercise is the cheapest way to find pre-existing bugs. M1 was merged with the workflow already failing; nobody had time to investigate because that's how the workflow had always behaved. The M2 review pressure ("wait for github action all pass") forced the issue and uncovered five distinct fixes. Worth budgeting for similar end-to-end exercises after future architecture changes.

### B.5 Discoverability gap in deferred MCP tools

While doing the MCP-native consumer sweep for M2, `find_callers`, `find_callees`, and `get_graph_slice` were **not** loaded as deferred tools through `ToolSearch` in Claude Code, even though they're registered server-side. Only `graph_update` came back. This is a real audit-tooling gap — the architecture explicitly names these tools as primary index queries, but auditors can't reach them through Claude Code without extra wiring.

This is filed as a future investigation rather than a plan-06 deliverable. It does not block any current workflow because `get_relevant_files` covers the most common case (semantic-similarity retrieval), but it would block deeper symbol-level investigations from being MCP-native.

### B.6 Phase C — Re-audit, status

Not run yet. Blocked on:
1. M1 + M2 must be in the live MCP server that Claude Code talks to. Both PRs are merged on master; the server picks up changes when the Claude Code session is (re)started.
2. The re-audit should ideally happen in a fresh Claude Code session so the deferred-tools list reflects the new schemas (including `task_id` on `task_status`, `include_context_bundle` on `get_relevant_files`).

Phase C acceptance criteria (from §6):
- Section-header clauses excluded from the actionable list (skill S8 effect — already applied)
- `get_relevant_files(..., include_context_bundle=False)` responses fit in the response budget
- `task_status` polling works for the next `graph_build`
- The actionable-unknown count drops from 10 to a much smaller number

Re-audit output should be saved to `.agent/artifacts/compliance_report_YYYYMMDD.md` (next-day date), preserving the 2026-05-19 baseline.
