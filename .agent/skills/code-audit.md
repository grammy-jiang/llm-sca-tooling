# SKILL: code-audit

Orchestrate design/spec compliance checks, bug resolution, patch review, and operational review using the `code-intelligence` MCP server.

---

## Preconditions

- The `code-intelligence` MCP server is running and the target repository is registered.
- A repository graph index exists (run `graph_build` or confirm via `repos` resource if not).
- For `bug-resolve`: a specific bug report or issue text is identified.
- For `implementation-check`: a design document, spec clause, or feature description is identified.
- For `patch-review`: a unified diff is provided.
- For `operational-review` or `readiness-audit`: a run record ID or repo ID is identified.

---

## Developer workflows

### `implementation-check`

Determine whether the current implementation satisfies a design/spec/feature clause.

**Entry point:** `run_implementation_check(design_ref="<doc_or_clause>", repos=[…])`

**Steps:**
1. Parse the design/spec into intent clauses (`kgacg` pattern) via the `implementation-check` MCP prompt.
2. Retrieve the `graph/{repo}/slice` and `summary/{repo}/{symbol}` resources for candidate symbols.
3. For each clause: generate an executable contract (JML/Semgrep/test predicate).
4. Run `run_static_analysis` over generated predicates; check verdict.
5. If static verdict is inconclusive and a reproduction exists: call `capture_trace` (async task) and use compressed trace as soft evidence.
6. Aggregate per-clause verdicts with the stage-7 aggregator; mark UNCERTAIN where confidence is low.
7. Record run events; write run record and harness-condition sheet.

**Verify gate:**
```
run_static_analysis        # fired predicates → SARIF
classify_patch_risk        # for any proposed fixes
make verify               # full gate on repo changes
```

---

### `bug-resolve`

Locate, explain, fix, and verify a reported bug.

**Entry point:** `run_issue_resolution(issue_text="<bug_report>", repos=[…])`

**Steps:**
1. `investigate` — retrieve memory hints, run `get_relevant_files`, fetch graph slice, load SARIF/build/test evidence.
2. Rank suspect locations with per-candidate reasoning (RGFL pattern).
3. If ambiguous and reproduction available: call `capture_trace` for compressed dynamic evidence.
4. `repair` — load graph slice for fault location; generate patch + pre/post-condition spec + execution-free certificate.
5. Run deterministic gates: SAST/SARIF delta, build/test, interface-contract compatibility.
6. Run `classify_patch_risk`; block if result is `vulnerable` or `vulnerability-introducing`.
7. Record trajectory to memory store on completion.

**Verify gate:**
```
run_static_analysis        # SARIF delta: original alert gone
make verify               # build/test pass
classify_patch_risk        # risk class: safe or correct-but-overfit only
```

---

### `patch-review`

Review an existing diff for correctness, safety, compatibility, and side effects.

**Entry point:** `run_patch_review(diff="<unified_diff>", context?="<description>", repos?=[…])`

**Steps:**
1. Load SARIF, graph slice, and interface contract resources for changed symbols.
2. Spawn 4-agent parallel review (Correctness / Security / Performance / Compatibility) via MCP Sampling when available.
3. Run deterministic gates: SAST delta, `classify_patch_risk`, contract compatibility, behavioural drift.
4. Aggregate verdicts: hard predicate firing is authoritative failure; soft votes require calibrated confidence.
5. Emit structured multi-axis report: functional ✓/✗, risk class, drift score, API/ABI flag, merge/block recommendation.

**Verify gate:**
```
classify_patch_risk        # risk class must be: safe or correct-but-overfit
run_static_analysis        # no new high/critical SARIF alerts
```

---

## Operator workflows

### `operational-review`

Reconstruct what happened in a run, verify policy/gate compliance, identify improvements.

**Entry point:** `run_operational_review(run_id="<run_id>")`

**Steps:**
1. Read `runs/{run_id}` resource and `runs/{run_id}/harness-condition` resource.
2. Read `operations/{repo}/ledger` for anomalies, budget overruns, repeated failures.
3. Check each stage: was a run record created? Were gates run? Were incidents logged?
4. Identify promotion opportunities: approved evidence → memory or lessons.
5. Emit review report with findings and recommended process improvements.

---

### `readiness-audit`

Decide whether the tool can run higher-autonomy workflows safely and usefully.

**Entry point:** `run_readiness_audit(repo="<repo_id>")`

**Steps:**
1. Read `readiness/{repo}` resource (latest readiness score across all 5 axes).
2. Read `governance/{repo}/policy` for effective permission profile.
3. Read `governance/{repo}/manifest-state` for drift state.
4. Check: harness stage, index freshness, SAST availability, test coverage, docs/spec links.
5. Emit readiness verdict: stage, per-axis scores, blockers, and next-stage upgrade path.

---

## Verify Gate (all workflows)

```
make verify                     # full verify gate must pass
run_static_analysis             # no new high/critical findings
local-agent-harness check .     # no harness drift
```

---

## Completion Criteria

- A run record (`runs/{run_id}`) and harness-condition sheet exist for the workflow.
- All deterministic gates passed or were documented as exceptions with human approval.
- For `bug-resolve` and `patch-review`: trajectory record written to memory store.
- For `implementation-check`: per-clause verdicts recorded with confidence and provenance.
- `make verify` exits 0.
- No new secrets or SAST findings.

---

## Notes

- **MCP Sampling:** parallel review subagents (Correctness/Security/Performance/Compatibility) require the MCP client to advertise `sampling` capability. If unavailable, audit runs in single-agent mode.
- **Graph index:** if `get_relevant_files` returns empty results, run `graph_build` first and retry.
- **Memory rejection:** low-utility memories (utility < threshold) are silently filtered; check memory resource if prior trajectory retrieval appears to produce no hints.
- **Uncertain verdicts:** UNCERTAIN clauses in `implementation-check` require human review before auto-passing release gates.
