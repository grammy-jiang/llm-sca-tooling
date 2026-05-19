# Plan 07 — Next session: Phase C re-audit + housekeeping + follow-ups

> **Date**: 2026-05-19
> **Purpose**: Self-contained playbook for the *next* Claude Code session. Readable cold by either a human or an agent — no reliance on prior chat history.
> **Predecessor**: `plan-06-audit-skill-and-mcp-server-fixes.md` (M1, M2, M3 — all merged).
> **Status of predecessor**: §6 Phase B1, B3, B4 met. Phase C **pending this session**.

---

## 0. Context (cold-start summary)

The 2026-05-19 audit of `evidence-sca` produced `.agent/artifacts/compliance_report_20260519.md` (gitignored, local-only). It identified three meta-findings against the `llm-sca-tooling` MCP server itself — the tooling the audit uses:

| # | Issue | Fix | Status |
|---|---|---|---|
| M1 | `task_status` / `task_result` / `task_cancel` schemas omitted `task_id` (advertised empty schema while handler required it). Schema-validating clients got `-32603 Internal error` on every call. | PR #1 (commit `882a8c5`): added `input_schema={task_id: string, required: [task_id]}` to all three descriptors + 9 regression tests. | **Merged** |
| M2 | `get_relevant_files` unconditionally inlined the full `ContextBundle` (0.4–1.3 MB per call), exceeding token budgets for MCP clients. | PR #2 (final commit `5047f0b`): added `include_context_bundle` arg; default `True` (compatibility — `context_bundle_ref` is not yet a fetchable resource); callers facing token-budget limits pass `False` to opt out. Plus 5 side-quest bug fixes (semgrep apt-install, uv-add-self, harness-status FileNotFoundError, --operational-gate-required, workflow template misplaced as live CI). | **Merged** |
| M3 | (Originally) score field carries derivation enum instead of a number. | **Retracted** — operator error; `combined_score: float ∈ [0, 1]` is in the response (`fl/models.py:63`). Documented in plan-06 §4 and SKILL.md change S9. | **Closed (no code)** |

Plus 14 audit-skill fixes (S1-S14) applied in place to `~/.claude/skills/audit/SKILL.md` and `~/.claude/skills/audit/references/mcp-workflow.md`. See plan-06 Appendix A.

Plus plan-06 itself landed in the tree via PR #3 (commit `952eb5e`, merged as `e4b21eb`).

**2026-05-19 prep-session outcomes** (work done after plan-07 was originally written, before the re-audit):

- Local `master` fast-forwarded to `llm-sca-tooling/master` (top is the PR #3 merge `e4b21eb`).
- Three feature branches `agent/m1-task-tool-schemas`, `agent/m2-get-relevant-files-bundle-opt-in`, `agent/m3-retraction-plan-06-refresh` deleted locally (all merged cleanly — `git branch -d` accepted all three).
- Pre-flight (§1.2) **failed** in the original prep session: `task_status` advertised `properties: {}` and `get_relevant_files` lacked `include_context_bundle`. Root cause was **not** a stale session — it was a stale *install*: the pipx-managed `llm-sca-tooling` binary at `~/.local/bin/` was pinned to PyPI `==0.6.2` (predates M1/M2).
- pipx reinstalled editably from this clone: `pipx install --editable . --force` from `/home/grammy-jiang/Documents/evidence-sca`. Hatchling editable `.pth` now resolves `import llm_sca_tooling` to this working tree's `src/` directory. M1 + M2 fixes verified in the live source (`tools.py:2702-2735` for M1, `tools.py:410,2287` for M2).
- See §6 (new appendix) for the diagnostic + reinstall recipe.

**What's left**: restart Claude Code so the MCP handshake re-resolves schemas, run pre-flight again to confirm, run the audit, verify acceptance, and update plan-06 §6.

---

## 1. Phase C — Re-audit (the main task)

### 1.1 Why a fresh session is required

Claude Code resolves the deferred-tool schemas at session start. The current session's schemas were resolved before M1 and M2 merged, so:

- `mcp__llm-sca-tooling__task_status` still advertises `properties: {}` (M1 unfix is visible)
- `mcp__llm-sca-tooling__get_relevant_files` still has no `include_context_bundle` arg (M2 unfix is visible)

Re-auditing from the old session would test the wrong contract. **Start a fresh Claude Code session in `/home/grammy-jiang/Documents/evidence-sca` before running the audit.**

### 1.2 Pre-flight: confirm the new contracts are visible

Before running `/audit`, do a 30-second sanity check from the fresh session:

```
# 1. Confirm M1 is visible (task_id parameter in task tool schemas)
Use ToolSearch with query: "select:mcp__llm-sca-tooling__task_status"
# Expected: schema shows properties: { "task_id": { "type": "string" } }, required: ["task_id"]
# If the schema still shows properties: {} — the MCP server didn't reload; close and reopen the session.

# 2. Confirm M2 is visible (include_context_bundle in get_relevant_files schema)
Use ToolSearch with query: "select:mcp__llm-sca-tooling__get_relevant_files"
# Expected: schema includes "include_context_bundle": {"type": "boolean"}
```

If either is missing, the MCP server is running an old build. Restart the Claude Code session (close and reopen the terminal/IDE pane that hosts it).

> **If a restart alone doesn't fix it**: the MCP server *install* is stale, not just the session's schema cache. The 2026-05-19 prep session hit this exact scenario — the running pipx binary was pinned to PyPI v0.6.2 (predates M1/M2), so no number of session restarts would help. See §6 for the editable-reinstall recipe. After the prep session, the install is editable from this clone, so a plain Claude Code restart is enough — but keep §6 handy for diagnosing future drift.

### 1.3 Run the audit

Invoke the skill with the same intent as the 2026-05-19 baseline:

```
/audit please read the design document and implementation plans in @docs/ and check the implementation completeness
```

The skill will:

- Register the repo via `mcp__llm-sca-tooling__register_repo`.
- Build the graph index (async; this time `task_status(task_id=...)` should actually work — M1).
- Assemble a focused spec from `docs/llm-sca-tooling-architecture.md` + `docs/llm-sca-tooling-implementation-plan.md` (likely the same "Named Architecture Surface Checklist" pattern used in the baseline).
- Run `mcp__llm-sca-tooling__run_implementation_check`.
- For each actionable unknown, call `mcp__llm-sca-tooling__get_relevant_files` — **pass `include_context_bundle=False`** so the responses fit the token budget (M2).
- Run `mcp__llm-sca-tooling__run_readiness_audit`.
- Synthesize `compliance_report_YYYYMMDD.md` (date-stamped per SKILL.md S12) under `.agent/artifacts/`.

### 1.4 Acceptance criteria (the actual point of Phase C)

Compare the new compliance report side-by-side against `.agent/artifacts/compliance_report_20260519.md`. The following must hold:

- [ ] **M1 effect verified**: graph-build polling actually completed via `task_status(task_id=...)`, no "Internal error" workaround needed (no notes in the report about polling being skipped because of M1).
- [ ] **M2 effect verified**: every `get_relevant_files` call's payload fit in the response budget (< 50 KB target on this repo); no notes about 1+ MB responses or offline JSON-slicing workarounds.
- [ ] **Skill S8 effect verified**: section-header clauses (the ones whose `text` is a pure markdown heading like `## MCP resources that MUST exist...`) are listed as **non-actionable** in §4, not padding the unknown count.
- [ ] **Actionable-unknown count drops materially**: the 2026-05-19 baseline had 10 actionable unknowns. The new report should have ≤ 2-3, ideally zero.
- [ ] **`combined_score` reported correctly**: the new `clause_investigation_YYYYMMDD.json` shows per-evidence `combined_score` (numeric in [0,1]) and `confidence` (enum) — both fields, both labelled correctly. (M3 was retracted because both were always there; this is just confirming the audit skill now reports them per SKILL.md change S9.)

### 1.5 Update plan-06 §6 with the result

After producing the new compliance report, edit `.agent/docs/plan-06-audit-skill-and-mcp-server-fixes.md` §6 acceptance criterion C:

- If all four criteria above are met: change `- [ ] **C**: ...` to `- [x] **C**: ...` and add a one-line link to the new compliance report.
- Append a short B.7 in Appendix B summarizing the re-audit outcome (count delta, surviving actionables, any new findings).

Commit and push as a small docs PR (similar to plan-06's landing PR #3).

### 1.6 If Phase C uncovers anything new

The re-audit is allowed to surface new findings — that's part of its job. Examples of what to do:

| Finding type | Action |
|---|---|
| A new server-side bug in `llm-sca-tooling` | Open a fresh `agent/<task-slug>` branch, fix per the plan-06 / M1 / M2 patterns. |
| A surviving actionable unknown that is *real* (e.g. `harness-condition-sheet.md` template genuinely missing) | Add to plan-08 (or plan-NN) as a product implementation-completeness follow-up. |
| A flaky audit-skill recipe (something in SKILL.md still confuses the agent) | Edit `~/.claude/skills/audit/SKILL.md` in place and record the S-fix in plan-06 Appendix A. |

---

## 2. Local housekeeping — DONE 2026-05-19

> **Status**: completed in the prep session. Left in the plan for traceability.

Sequence executed:

```bash
git fetch llm-sca-tooling --prune          # pruned m1/m2/m3 remote-tracking refs
git checkout master
git merge --ff-only llm-sca-tooling/master # 610dd54..e4b21eb (PR #3 merge)
git branch -d agent/m1-task-tool-schemas
git branch -d agent/m2-get-relevant-files-bundle-opt-in
git branch -d agent/m3-retraction-plan-06-refresh
```

All three `git branch -d` calls succeeded (no `-D` needed — all branches cleanly merged). Two unrelated older branches remain (`agent-mcp-stdio-uv-cache`, `agent/gap-implementation-batch1`) — out of scope for plan-07, left alone.

The orphan branch on `origin` (the `grammy-jiang/evidence-sca` remote, which lives at v0.2.5 and is divergent from the active `llm-sca-tooling` remote at v0.6.2+) was already deleted earlier. No cleanup needed there.

---

## 3. Follow-up threads (pick up after Phase C closes)

Each row below is a candidate plan-08, plan-09, etc. Not blocking Phase C.

### 3.1 M2 architectural follow-up — real `context-bundle` resource

**Why**: M2 currently leaves `include_context_bundle=True` as the default because `context_bundle_ref` returns `{"kind": "inline", "file_count": N}` from `fl/localisation.py:56` — metadata, not a fetchable URI. Anyone following the architecture's "Large-resource rule" expects the default to be `False` with a real reference. Today's behaviour is honest (zero false promises) but not architecturally complete.

**Scope sketch**:
- Register a `context-bundle` MCP resource (URI scheme `code-intelligence://context-bundle/{bundle_id}`).
- Persist the bundle when produced, keyed by a hash of `(issue_text, repos, snapshot)` so identical queries return the same ID.
- Have `LocalisationResult.context_bundle_ref` populate the actual URI when the resource is registered.
- Once the URI is real, flip `include_context_bundle` default to `False` (with a one-cycle deprecation warning if anyone has come to rely on inline payload).
- Add eviction / GC policy for the bundle store.

**Risk**: medium. Adds new persistent state. Worth its own design doc before coding.

**Trigger to start**: any time after Phase C is clean.

### 3.2 Deferred-tool discoverability gap

**Why**: While doing the MCP-native consumer sweep for M2, `find_callers`, `find_callees`, and `get_graph_slice` did **not** load as deferred tools via `ToolSearch` in Claude Code. Only `graph_update`, `register_repo`, `run_*`, `get_relevant_files`, and the task tools were available. The architecture explicitly names the missing tools as primary symbol-level queries.

**First investigation**: from a fresh Claude Code session, run `ToolSearch` with query `"find_callers"` (and the others). If they don't surface, look at:
- Are they registered with a tier that the default `list_tools()` filter excludes? `tier_registry` in `src/llm_sca_tooling/mcp_server/tools.py`.
- Is there a Claude Code tool-prefix filter excluding them?
- Is the JSON-RPC `tools/list` response truncating?

**Trigger to start**: if Phase C re-audit needs symbol-level investigation (e.g. confirming which Python module implements `compute_readiness_score`) and falls back to `get_relevant_files` to approximate, that's the cue to fix this.

### 3.3 Original 10 actionable unknowns from 2026-05-19

After Phase C, whichever clauses still surface as actionable unknowns are real product completeness questions. The baseline list:

- `clause:316c35512bd4` — MCP Sampling capability negotiation
- `clause:fd9276eb7954` — Graph schema node types
- `clause:c0d662ac95a2` — Graph schema edge types
- `clause:3a1e97ba249e` — Provenance fields with derivation enum
- `clause:34a4a91f2e10` — Harness Condition Sheet template
- `clause:6ad5c847e8ee` — Parseable run-record schema
- `clause:1d71b248483b` — Manifest regression test skeletons
- `clause:109aea1b2706` — Operational review and incident record templates (was satisfied with 0.85 confidence in the baseline)
- `clause:7ba193b6ee52` — Five-axis AI-readiness rubric with stage gates (was partially_satisfied 0.60)
- `clause:fc749029c776` — Harness drift classifier (was partially_satisfied 0.50)

Most of these likely WILL be satisfied by the re-audit because the original problem was retrieval bias (docs ranked above src/), not missing implementation. The interesting cases are the ones that survive — those are real Phase 19 / future work candidates.

### 3.4 Two-remote reconciliation

**Why**: `git remote -v` shows two remotes — `origin → grammy-jiang/evidence-sca` (last release v0.2.5; stale) and `llm-sca-tooling → grammy-jiang/llm-sca-tooling` (active, v0.6.2+). They share no common ancestor on `master`. This split has been working but is an accident waiting to happen (someone pushes to the wrong one, etc.).

**Options**:
- Archive `grammy-jiang/evidence-sca` on GitHub (mark read-only) so accidental pushes fail.
- Make `llm-sca-tooling` the local `origin` and rename the current `origin` to `evidence-sca-archive`.
- Or formally merge them if the divergence is intentional (probably not — they share a project name).

**2026-05-19 update**: while diagnosing pre-flight in the prep session, also discovered a leftover **user-site editable install** at `~/.local/lib/python3.14/site-packages/` (v0.1.0, editable-linked to `/projects/evidence-sca`). Not on PATH, not used by pipx — dead weight, but makes `pip show llm-sca-tooling` (run outside the pipx venv) report misleading info. Trivial cleanup as part of this thread: `pip uninstall llm-sca-tooling` against user-site Python (the one used outside pipx).

**Trigger to start**: any time. Low urgency, but worth doing before adding more contributors.

### 3.5 Skill change visibility

The 14 audit-skill fixes (S1-S14) were applied in place to `~/.claude/skills/audit/SKILL.md` and `~/.claude/skills/audit/references/mcp-workflow.md`. Those files live in the user's global Claude config, not this repo. If the skill is ever shared (published, copied to another machine, used by another developer), the fixes are tied to this specific machine.

**Action** (low priority): if the audit skill is intended to be reusable beyond this machine, copy the fixed SKILL.md + mcp-workflow.md into a versioned location in this repo (e.g. `.agent/skills/audit/`) so the fixes propagate.

---

## 4. Session bootstrap checklist (for the fresh session)

```
[x] Open Claude Code in /home/grammy-jiang/Documents/evidence-sca        (2026-05-19 prep)
[x] Confirm latest master: git log --oneline -3 shows PR #3 merge        (master at e4b21eb)
[x] Run housekeeping from §2 — sync master, delete merged branches       (2026-05-19 prep)
[x] Reinstall pipx editable from this clone (§6)                          (2026-05-19 prep — extra step
                                                                           not in original plan)
[ ] **Restart Claude Code session** so MCP handshake re-resolves schemas
[ ] Pre-flight from §1.2: ToolSearch shows task_id in task_status schema and
    include_context_bundle in get_relevant_files schema
[ ] Run /audit (§1.3)
[ ] Verify acceptance criteria (§1.4) against the new compliance report
[ ] Update plan-06 §6 + add Appendix B.7 (§1.5)
[ ] Pick a follow-up thread from §3 if there's appetite for more work
```

The bold restart step is the *only* manual setup gating the next session. After restart, the next session should be able to read this plan cold and proceed from the pre-flight checkbox.

---

## 5. Hand-off note

This plan is in `.agent/docs/` so it's tracked-eligible but currently untracked (consistent with plan-01..05 in this directory). Commit it if you want it to propagate to other clones; otherwise it stays as a working note. Either way, it's readable cold.

As of 2026-05-19, plan-07 has been updated with the prep-session outcomes (§0, §1.2 recovery note, §2 marked done, §3.4 user-site install confounder, §4 checklist progress, and a new §6 install-mechanism appendix). Re-evaluate whether to commit at the end of the next session (after the §1.5 updates land).

---

## 6. Appendix — MCP server install mechanism (recipe)

> Added 2026-05-19 after the prep session discovered the pipx install was stale at PyPI v0.6.2.

The MCP server CLIs Claude Code talks to on this machine are **pipx-managed**, not bare-pip-user or uv-tool. This matters when pre-flight from §1.2 fails *even after* a Claude Code restart — that means the running binary points at the wrong source, not just that the session's schema cache is stale.

### 6.1 Diagnose (read-only)

```bash
# 1) Confirm the running binary uses the pipx venv's Python:
head -1 ~/.local/bin/llm-sca-tooling
# expected: #!/home/grammy-jiang/.local/share/pipx/venvs/llm-sca-tooling/bin/python

# 2) What's pipx tracking?
pipx list | grep -A1 llm-sca-tooling
#   "package llm-sca-tooling X.Y.Z, installed using Python 3.14.4"

# 3) Where is pipx linked? (source path or PyPI pin?)
cat ~/.local/share/pipx/venvs/llm-sca-tooling/pipx_metadata.json | \
  python3 -c "import json, sys; m=json.load(sys.stdin)['main_package']; \
              print('source:', m.get('package_or_url'))"
#   editable from clone: a filesystem path
#   pinned from PyPI:    "llm-sca-tooling==X.Y.Z"

# 4) Cross-check: is hatchling's editable .pth present?
~/.local/share/pipx/venvs/llm-sca-tooling/bin/python -m pip show llm-sca-tooling | grep Editable
#   present:  "Editable project location: /home/grammy-jiang/Documents/evidence-sca"
#   absent:   non-editable install (snapshot)

# 5) Verify a specific fix is in the linked source:
~/.local/share/pipx/venvs/llm-sca-tooling/bin/python \
  -c "import llm_sca_tooling; print(llm_sca_tooling.__file__)"
# then grep that directory for the expected fix
```

### 6.2 Reinstall editably from this clone

```bash
cd /home/grammy-jiang/Documents/evidence-sca
pipx install --editable . --force
# verify with §6.1 steps 3+4 — should now show this clone's path + editable marker
# then close + reopen Claude Code so the MCP handshake reloads tools/list
```

`pipx install --editable . --force` reuses the existing pipx venv (same `~/.local/bin/llm-sca-tooling` path) but replaces what the venv imports. No PATH changes, no other tools affected.

### 6.3 Confounder to ignore (until §3.4 cleans it up)

A leftover **user-site** install exists at `~/.local/lib/python3.14/site-packages/` (v0.1.0, editable-linked to `/projects/evidence-sca`). It is **not on PATH** and **not what pipx runs**, but it makes `pip show llm-sca-tooling` (run outside the pipx venv) report misleading info — specifically, an older version and a different editable source. Diagnostic step 1 above (`head -1 ~/.local/bin/llm-sca-tooling`) is the disambiguator: the shebang reveals which Python actually runs the MCP server, and from there everything else falls into place.

### 6.4 Why a Claude Code restart alone isn't always enough

A restart re-runs the MCP handshake, which re-reads `tools/list` and refreshes deferred-tool schemas in Claude Code's session. That works *if* the MCP server binary already serves the right code. When the pipx venv is pinned to an older PyPI release (or links to a stale clone), the binary keeps serving the old code regardless of how many times you restart Claude Code. Pre-flight §1.2 is what distinguishes the two failure modes — and the prep session caught exactly the install-stale case that the original plan didn't anticipate.

This recipe is also stored as a reference memory at `~/.claude/projects/-home-grammy-jiang-Documents-evidence-sca/memory/reference_mcp_install_layout.md`, so future sessions across any project on this machine can consult it without re-reading plan-07.
