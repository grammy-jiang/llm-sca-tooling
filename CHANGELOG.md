# Changelog

All notable changes to `llm-sca-tooling` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.6.3] — 2026-05-19

### Changed

#### MCP symbol-query tools are default-discoverable (plan-07 §3.2)

- **`get_graph_slice`**, **`find_callers`**, **`find_callees`** promoted
  from `tier=3` to `tier=1` in `mcp_server/tools.py`. The default
  `tools/list` filter in the MCP handshake exposes tiers 1–2 only, so
  tier-3 placement made these architecture-primary symbol-level queries
  invisible to schema-validating clients (Claude Code's deferred-tool
  discovery, in particular). The Phase C re-audit on 2026-05-19 hit
  this exact gap: auditors fell back to `get_relevant_files`
  (keyword + graph-neighbour signals) and could not run symbol-level
  follow-up queries. The fix surfaces them by default; no callers
  required to opt in.

#### Issue-text file mention extraction (`fl/issue.py`)

- **`normalize_issue_text`** now recognises a much broader set of file
  paths inside issue text:
  - Adds extensions: `.json`, `.yaml`/`.yml`, `.toml`, `.md`,
    `.tsx`, `.jsx`. Previously only `.py`/`.ts`/`.js`/`.cpp`/`.cc`/
    `.cxx`/`.hpp`/`.h`/`.idl` were extracted.
  - Adds support for leading-dot paths like
    `.agent/templates/harness-condition-sheet.md`.
  - Uses a negative-look-behind boundary so trailing punctuation no
    longer pollutes the captured path.
- Phase C surfaced this as a retrieval gap: direct queries for the
  harness-condition-sheet template and run-record schema returned
  mostly `docs/*.md` because the extractor never recognised the exact
  `.agent/templates/*.md` / `schemas/*.schema.json` paths the issue
  text mentioned.

### Fixed

#### `RunRecordWriter` no longer hangs on file I/O

- Removed `asyncio.to_thread` wrappers from `RunRecordWriter.create_run`,
  `append_event`, and `close_run` in `operations/run_records.py`. The
  writes are short, local, and synchronous; the thread-pool offload was
  unnecessary and could hang in sandboxed environments where the
  default executor was constrained. Behaviour for callers is
  unchanged — the methods are still `async def`.

#### Makefile `detect-secrets` serial fallback

- **`Makefile`**: the `secrets` phase now retries with an in-process
  serial scanner when the parallel `detect-secrets scan` invocation
  reports `Operation not permitted`. Normal environments still use
  the native parallel path. The fallback only kicks in when
  multiprocessing is blocked (some sandboxes, restricted container
  runtimes); without it `make verify` could fail with a
  non-actionable error.

### Tests

- **`tests/fl/test_phase9_fl.py::test_issue_normalizer_extracts_docs_schema_and_template_paths`**
  — pins the new extensions and leading-dot path support.
- **`tests/mcp_server/test_task_tool_schemas.py::test_symbol_query_tools_are_default_discoverable`**
  — pins that the three symbol-query tools appear in the default
  tier-1/2 `tools/list` output, so a future tier regression cannot
  silently re-hide them.

### Verified

- `make verify-fast` passed.
- `make verify` passed for format/imports/types/tests/security
  (detect-secrets via the new fallback path; `pip-audit` requires
  network egress and is run in CI).
- `make _sast` (Bandit) reported no medium/high issues.
- `make verify-dirty` confirmed `uv.lock` and `.secrets.baseline`
  unchanged by the verify path.

### Docs

- **`.agent/docs/plan-06-audit-skill-and-mcp-server-fixes.md`** §6 and
  Appendix B.7 record the Phase C re-audit outcome on 2026-05-19:
  M1/M2/M3 mechanics verified, but criterion C remains open because
  MCP relevance is still doc-biased (`signals_missing: ["EMBEDDING"]`)
  and the focused probe surfaced 19 unknowns rather than dropping
  toward zero.
- **`.agent/docs/plan-07-next-session-re-audit-and-followups.md`** lands
  in-tree (was previously a local working note) as the playbook this
  release executed against.

---

## [0.6.2] — 2026-05-19

### Added

#### Adversarial-fixture breadth (Phase 18 §8)

The Phase 18 adversarial suite grew from 6 → 10 fixtures.  Phase 18 §8.2
specifies one fixture per category as the **floor**; this release
doubles the four highest-value categories (prompt injection, scope
write, policy bypass, reward hacking) with within-category variants
that single fixtures don't capture.

- **`adv:indirect-prompt-injection`** (`check_type=prompt_injection`)
  — **indirect** injection where an attacker plants the payload in a
  document the agent reads.  Distinct from the direct prompt-injection
  fixture above; indirect injection is the harder-to-catch variant and
  was the priority gap flagged in Plan 05.
- **`adv:scope-write-symlink`** (`check_type=out_of_scope_write`) —
  symlink-traversal write that simple path-prefix scope checks miss.
  Pins the resolved-target check.
- **`adv:policy-bypass-test-mode`**
  (`check_type=multistep_policy_bypass`) — common real-world bypass
  shape: agent is offered an escape hatch ("skip the check in
  test/dev mode").  Pins refusal even when an escape hatch is offered.
- **`adv:reward-hack-test-only-fix`**
  (`check_type=reward_hackable_task`) — reward-hacking variant where
  the proposed patch deletes or weakens the failing test instead of
  fixing the underlying defect.

`default_adversarial_fixtures()` extended; `run_adversarial_suite()`
now returns 10 results.  Adversarial-gate runtime is still
milliseconds — the suite is a deterministic check, not a runtime probe,
so each new fixture adds negligible cost.

### Changed

- **`tests/evaluation/fixtures/README.md`** updated in the same
  commit per Plan 04's convention ("if a fixture is added/renamed,
  update this README in the same commit").  All 10 adversarial
  fixtures are now documented with check_type, expected_outcome, and
  what each exercises.

### Tests

- Existing `test_adversarial_suite_and_production_refresh` updated:
  expected fixture count 6 → 10.
- Four new per-fixture regressions:
  `test_adversarial_indirect_prompt_injection_passes`,
  `test_adversarial_scope_write_symlink_passes`,
  `test_adversarial_policy_bypass_test_mode_passes`,
  `test_adversarial_reward_hack_test_only_fix_passes`.
  One-per-fixture so a single failure points at the specific attack
  shape rather than the whole suite.

### Verified

- `make verify` exits 0; all release-suite tests pass.
- `make release-gate` exits 0 with 10/10 adversarial fixtures passing
  (was 6/6 in v0.6.1).

### Design choice — fixture set

Chose the **Top-4** set (10 total) over the Broader-6 (12 total)
alternative.  Rationale: 10 fixtures double the categories that
matter most for real-world failure modes; 12 would also cover
`document_injection` and `tool_boundary_misuse` variants but those
remain less common attack shapes and can wait for a follow-up
expansion if needed.  Format note: F-inline (Python dict per
fixture); the same fixture-format-revisit-at-N principle that applies
to calibration oracles applies here, but with N for adversarial set
arguably higher since these are pure schedule entries, not data.

---

## [0.6.1] — 2026-05-19

### Added

#### First Phase 18 calibration fixture — SARIF disappear

- **`CalibrationOracle`** model added to
  `llm_sca_tooling.release.models`.  Wraps a `CalibrationSample` with a
  `clause_text_pattern` (substring) that the impl-check aggregator
  consults during the auto-pass gate.  Exported via the module's
  `__all__`.
- **`llm_sca_tooling.release.fixtures.calibration.sarif_disappear.ORACLE`**
  — the project's first Phase 18 §5 calibration fixture.  Pattern
  `"alert must disappear"`, `family="behavioural:sarif-disappear"`,
  `predicted_probability=0.95`, both labels `"satisfied"`.  Asserts
  that `sarif/delta.py::compute_sarif_delta` satisfies the
  "original alert must disappear before the alert is considered fixed"
  behavioural clause.  Format note: F-inline pending refinement at
  fixture count ≥ 3 (next-fixture decision: YAML or JSONL).
- **`llm_sca_tooling.release.calibration_fixtures`** — loader module
  exposing `default_calibration_oracles()` and
  `default_calibration_samples()`.

### Changed

#### impl-check — calibrated-oracle rescue in aggregator

- **`aggregate_verdicts`** gains an optional `calibration_oracles`
  parameter and a new Rule 5 ("calibrated-oracle rescue"): when
  `calibration_available=True`, the clause's risk_class is not
  `{"security", "compliance"}`, and an oracle's `clause_text_pattern`
  is a substring of the clause's text, the clause is returned as
  `satisfied` with `dominant_evidence="calibrated_oracle"`,
  `auto_pass_gate_passed=True`, and `ece_bucket` derived from the
  oracle's `predicted_probability`.
- **`run_implementation_check`** gains a `calibration_oracles`
  parameter; when omitted and `calibration_available=True`, it falls
  back to `default_calibration_oracles()` (lazy import to avoid a
  module-load cycle).
- **`mcp_server.tools.run_implementation_check`** now accepts a
  `calibration_available: bool` argument (default `False`) on both the
  sync and `task=true` code paths.  Without this exposure the new
  oracle path is unreachable from MCP / CLI consumers.
- **`run_release_gate`** now appends the oracle-derived samples from
  `default_calibration_samples()` to `impl_check_samples`, so oracle
  samples contribute to the release-gate's calibration metrics.

### Tests

- `tests/release/test_calibration_fixtures.py` (5 tests):
  - `test_sarif_disappear_fixture_exists` — oracle is registered and
    its pattern matches the canonical SARIF-disappear spec.
  - `test_sarif_disappear_clause_becomes_satisfied_with_calibration`
    — end-to-end: clause unknown without calibration, satisfied with.
  - `test_calibrated_oracle_marker_set_on_matched_clause` — aggregator
    sets the `calibrated_oracle` evidence marker and auto-pass flag.
  - `test_default_calibration_samples_feeds_release_gate_corpus` —
    sample list is non-empty and self-consistent.
  - `test_security_clause_is_not_auto_passed_by_oracle` — Phase 18
    §5 rule: security / compliance clauses still require hard evidence.

### Audit signal effect (May-17 spec, calibration_available=True)

| Metric | v0.6.0 | v0.6.1 | Δ |
|---|---|---|---|
| satisfied | 91 | 92 | +1 |
| violated | 0 | 0 | 0 |
| unknown | 45 | 44 | -1 |

The SARIF-disappear clause moves from unknown to satisfied via the
new calibrated-oracle path.  Small delta in absolute count, but this
is the first concrete calibration delta in the project's history —
the calibration mechanism is now demonstrated end-to-end (oracle
fixture → loader → aggregator → MCP tool → audit driver).

### Verified

- `make verify` exits 0; full suite passes including 5 new
  calibration-fixture tests.
- `make release-gate` exits 0; the release-gate's calibration report
  now also consumes the oracle-derived samples.

---

## [0.6.0] — 2026-05-18

### Changed

#### impl-check — section-header pseudo-clauses filtered at extraction

- **`clause_extractor._is_section_header`** — new H-tight heuristic.  A
  line is treated as a section header (and excluded from extraction)
  iff (a) its text ends in `:` AND (b) the next non-empty line in the
  original document starts with a bullet marker (`-`, `*`, `+`, or
  `1.` / `2.` / `3.`).  Section headers like "The implementation must
  register the following MCP resources:" are syntactic introductions
  to a list, not verifiable obligations; the real obligations are the
  bullets they introduce, which continue to be extracted individually.

- **`clause_extractor._extract_normative_clauses`** refactored to be
  line-aware so the lookahead in `_is_section_header` has access to
  the next non-empty line.  Only the *last* sentence on a line can be
  a section header (the lookahead targets the next line, not the next
  sentence on the same line), so earlier sentences on a multi-sentence
  line are unaffected.  The unused private helper `_split_sentences`
  is removed.

- **Counter-test `test_obligation_ending_in_colon_without_bullets_is_kept`**
  pins H-tight over the simpler `endswith(":")` form so obligations
  that legitimately end in `:` (e.g. "The verdict must be one of:
  satisfied, violated, unknown.") are not dropped.

#### Audit signal effect (May-17 spec, in-repo audit driver)

Re-running the in-repo audit against `.agent/artifacts/audit_spec_20260517.md`:

| Metric | v0.5.1 | v0.6.0 | Δ |
|---|---|---|---|
| satisfied | 91 | 91 | 0 |
| violated | 0 | 0 | 0 |
| unknown | 48 | 45 | -3 |

The three filtered clauses are exactly the colon-ended section headers
("register the following MCP resources / public prompts / private
workflow templates"), with zero false positives (no clause appeared in
v0.6.0 that wasn't already in v0.5.1).  The change is smaller than the
planning estimate of `~10` because the audit spec contains only four
`:`-ended lines total (one of which is a non-normative fragment).  The
remaining 45 unknowns are genuine calibration-pending obligations
(e.g. "Every implementation phase declares its Harness Condition
Sheet.", "All schema objects round-trip through JSON.") and are
Plan 03 / calibration-fixture work, not extraction-filter work.

### Tests

- `test_section_header_introducing_list_is_not_extracted` — pins the
  new filter.
- `test_obligation_ending_in_colon_without_bullets_is_kept` —
  counter-test guards the H-tight heuristic against over-filtering.

### Verified

- `make verify` exits 0; full impl_check suite (26 tests) passes.
- `make release-gate` exits 0; 0 failing gates, identical numbers to
  v0.5.1 (T3 resolve 1.00, T4 resolve 1.00, 6/6 adversarial pass).

### Note on clause IDs

Clause IDs for normative-strategy clauses change in v0.6.0 because the
refactor computes byte-accurate per-line spans rather than the previous
flat running offset.  Within-run ID stability (re-extraction yields the
same IDs) is preserved.  Consumers that pinned specific v0.5.x normative
clause IDs will need to re-extract; the audit re-run captured above
reflects this.

---

## [0.5.1] — 2026-05-18

### Added

#### impl-check — clause text + uncertainty_reason in report

- **`ImplementationCheckReport.unknown_clause_details`** and
  **`violated_clause_details`** — parallel structured fields to the
  existing `unknown_clauses` / `violated_clauses` ID lists.  Each entry
  carries:
  - `clause_id` — matches the ID in the legacy list
  - `text` — the actual clause text from the spec
  - `final_verdict` — "unknown" or "violated"
  - `uncertainty_reason` — categorical reason ("calibration_absent",
    "unverifiable", "insufficient_evidence", etc.)
  - `dominant_evidence` — stage-level evidence label
  - `confidence` — record-level confidence

  Additive (non-breaking): the ID lists stay as `list[str]` so existing
  consumers keep working without changes.

- **`ClauseUncertaintyDetail`** model added to
  `llm_sca_tooling.impl_check.models` (exported via the module's
  `__all__`).

### Verified

- `make verify` exits 0; 63 tests pass across impl_check / mcp_server
  / release / evaluation suites.
- `make release-gate` continues to pass (overall pass, 0 failing gates).
- Re-audit against v0.5.0 fixtures confirms 48 / 48 unknowns now carry
  detail; all share `uncertainty_reason: "calibration_absent"`,
  `dominant_evidence: "no_hard_evidence"`.  See
  `.agent/docs/plan-02-clause-extractor-section-header-filter.md`
  for the planned follow-up that drops the unknown count.

---

## [0.5.0] — 2026-05-18

### Added

#### Release gate — real T3/T4 wiring (Phase 18 Track A)

- **`release_gate.run_release_gate()`** orchestrates the Phase 18 release
  gate by actually invoking `run_t3_null` and `run_t4_null` against the
  in-repo fixtures, deriving real `CalibrationSample`s from each
  fixture's predicted/gold pairs, and feeding the resulting
  `CalibrationReport`, `BenchmarkSuiteResult` list, operational gate
  result, and adversarial check results into `ReleaseGateEvaluator`.
  Replaces `build_passing_fixture_release_gate` as the production code
  path. The fixture-builder is kept for unit-testing the evaluator only.
- **CLI `llm-sca-tooling release-gate`** (and the Phase-19 wrapper
  `release gate`) now call `run_release_gate`; the report carries
  runner-issued `eval_run_id`s and `harness_condition_id` instead of
  fixture sentinels.
- **`make release-gate`** Makefile target runs the gate and writes the
  `ReleaseGateResult` to `.agent/eval/runs/<UTC-timestamp>/release_gate_report.json`.
  Intentionally **not** part of `make verify` so commit-time stays fast;
  required before `git tag` per the release procedure.
- **`tests/release/test_release_gate_e2e.py`** — 4 e2e tests pinning the
  contract: distinct gate_run_id across calls, runner-issued eval_run_ids
  (not `:fixture`), persistence to `<report_dir>/release_gate_report.json`,
  and overall pass against the in-repo fixtures.

#### Release-gate report dir gitignored

- **`.gitignore`** now ignores `.agent/eval/runs/` so release-gate reports
  (which carry per-run identifiers) stay local and do not enter the
  repo by accident.

#### Benchmark integration plan

- **`.agent/docs/benchmark-integration-plan.md`** — durable design
  record explaining what Track A delivers, why downloading external
  benchmarks was *not* the right move (Phase 10 §3 non-goal, HC5 egress,
  Phase 18 §4 "-style" fixture intent), and where Track B's audit
  landed (Phase 18 §4 minimums verified met — no backfill needed).

### Changed

#### Circular import fix in `evaluation.t4_runner`

- **`evaluation/t4_runner.py`** moved the `release.calibration` /
  `release.models` imports inside `_aggregate_t4_metrics` to break a
  top-level cycle that surfaced when test modules import `release.release_gate`
  before any other package member.

### Release-gate metrics (v0.5.0)

All numbers from the real `run_release_gate` invocation against the
in-repo fixtures (null backend, no LLM in the loop):

| Suite | Instance count | Resolve-rate proxy | Passed |
|---|---|---|---|
| `t3-cross-language` | 5 | `cross_language_fl_top1 = 1.00` | ✅ |
| `t4-implementation-spec` | 5 | `clause_accuracy = 1.00` | ✅ |

| Gate | Status |
|---|---|
| Benchmarks | ✅ pass |
| Calibration (ECE, macro-F1, repo-QA, memory ship) | ✅ pass |
| Operational (trace, policy, budget, maintainability, manifest, readiness) | ✅ pass |
| Adversarial (6 fixtures: prompt injection, doc injection, tool boundary, out-of-scope write, multistep bypass, reward-hackable) | ✅ pass (6/6) |
| Memory ship | ✅ pass |
| AI-readiness | ✅ attached |
| **Overall** | ✅ **pass** |

Caveat: the null backend trivially passes every fixture; the numbers
above demonstrate that the *gate machinery is sound*, not that the
tool is accurate against arbitrary inputs. Real-LLM backends will
exercise the gate's filtering. The fixtures are designed per Phase 18
§4 to let a correctly-implemented tool pass its own gate.

---

## [0.4.4] — 2026-05-18

### Fixed

#### impl-check — run-record harness_condition_id linkage (May-17 audit Finding 5)

- **`storage.OperationsService.close_run`** now accepts an optional
  `harness_condition_id` parameter and persists it onto the
  `RunRecordRow`. Previously the column stayed `None` even after a
  successful impl-check, so `code-intelligence://runs/{run_id}` returned
  `harness_condition_id: null`.
- **MCP `run_implementation_check`** records the harness condition sheet
  via `record_harness_condition` and propagates the id to `close_run`,
  closing both the run-record column and the
  `code-intelligence://runs/{run_id}/harness-condition` resource.
- **`impl_check.run_implementation_check`** now exposes the HCS payload
  via the artifact sink under `harness-condition://{hcs_id}` so MCP
  servers (and future workflows) can persist it.

### Added

#### Indexing — governance path allowlist (May-17 audit Finding 3)

- **`IndexingConfig.governance_allowlist`** indexes hidden directories
  that hold governance contracts (`.agent`, `.agents`, `.codex`,
  `.github`) by default, so implementation-check evidence can cite them.
- **`IndexingConfig.governance_blocklist`** unconditionally skips
  `credentials/` and `secrets/` directories. Secret file patterns
  (`.env`, `.env.*`, `*.key`, `*.pem`) are blocked at the file level
  regardless of `include_hidden`. Honours HC6.

#### Indexing — Markdown backend (May-17 audit Finding 4)

- **`MarkdownBackend`** (`indexing/backends/markdown.py`) emits one
  `document` GraphNode per heading with a `SourceSpan` carrying
  `start_line` / `end_line`. Heading text, level, and breadcrumb path
  (`README#Top > Mid > Leaf`) are stored in node properties so
  `get_relevant_files` can return exact `file:line` evidence for
  Markdown clauses. Uses `markdown-it-py` (already a dependency) to
  correctly skip headings inside fenced code blocks.
- Wired into the `graph_build` and `graph_update` orchestration paths
  in `IndexingService`.

### Tests

- `test_run_implementation_check_links_harness_condition_id` —
  regression for Finding 5.
- `test_ignore_policy_governance_allowlist_indexes_dot_dirs` and
  `test_ignore_policy_blocks_secret_dirs_and_files` — regression for
  Finding 3.
- `tests/indexing/test_markdown_backend.py` — 5 tests covering heading
  emission, fenced-code skipping, breadcrumb qualified names, empty
  files, and capability reporting (Finding 4).

---

## [0.4.3] — 2026-05-17

### Added

#### Codex CLI overlay

- **`.codex/INSTRUCTIONS.md`**: Codex CLI-specific supplement declaring
  default approval mode (`suggest`), max turns (40), sandbox devcontainer,
  session transcript path, and a non-relaxation declaration that defers all
  HC1–HC6 hard constraints to `AGENTS.md`.

#### MCP server — regression test for path-based repo argument

- **`test_run_readiness_audit_persists_when_repo_arg_is_path`**: regression
  test verifying that passing a filesystem path (not a `repo_id`) as the
  `repo` argument to `run_readiness_audit` still persists the report and
  emits a resource-updated notification. Covers the case where
  `_resolve_readiness_repo_record` previously returned `None` for path inputs.

---

## [0.4.2] — 2026-05-17

### Fixed

#### MCP server — resources `listChanged` and readiness audit persistence

- **`resources.listChanged`** set to `true` in both `McpServerCapabilities` and
  the stdio transport capabilities dict; clients that subscribe to resource
  lists now receive change notifications correctly.
- **`run_readiness_audit`** persists the report to the workspace database and
  emits a `code-intelligence://readiness/<repo_id>` resource-updated
  notification on completion (both immediate and task-async paths). The tool
  registration now declares `notifications=True`.

#### impl-check — clause extractor includes structural architecture bullets

- Bullet clauses no longer require a backtick-delimited code symbol; items
  containing structural architecture terms (`adapter`, `task`, `workflow`,
  `schema`, `sarif`, `harness`, `readiness`, `persist`, `emit`, etc.) are
  now included. This captures design and roadmap obligations that use plain
  prose rather than symbol references.
- Added `_STRUCTURAL_BULLET_PATTERN` and `_REFERENCE_BULLET_PATTERN` guards
  to keep generic prose out while preserving auditable design clauses.

#### SARIF / bandit adapter — scan `src/` when present

- New `_scan_root()` helper returns `repo_root/src` if that directory exists,
  falling back to `repo_root`. `_run_bandit` and `_run_json_fallback` now
  pass `scan_root` as the target path and `cwd` as the working directory
  separately, preventing bandit from scanning vendored or generated directories
  outside `src/`.

#### Build — detect-secrets excludes its own baseline file

- `make secrets` now passes `--exclude-files '^\.secrets\.baseline$'` to
  prevent detect-secrets from flagging hashed entries inside the baseline
  itself as new secrets.

---

## [0.4.1] — 2026-05-17

### Changed

#### Build — verify gate observability and non-mutating security checks

- **`make verify` split into named phases**: `verify-format`, `verify-lint-imports`,
  `verify-types`, `verify-tests`, `verify-security`, `verify-dirty`. Each phase
  emits `[verify] start <phase>` / `[verify] done  <phase> elapsed=Xs` so
  operators can distinguish a silent scanner from a hung process.
- **`--frozen` flag** added to all `uv run` invocations in the verify path;
  `uv.lock` can no longer be mutated by running `make verify`.
- **`detect-secrets` made non-mutating**: now scans to a temp file and compares
  hashed secrets against the existing baseline in Python. `.secrets.baseline`
  is never rewritten during verification.
- **`verify-dirty` post-verify guard**: runs `git diff --exit-code` on `uv.lock`
  and `.secrets.baseline` as the final verify step; fails if either was mutated.
- **Fast iteration targets** added: `make verify-fast` (format + imports + types,
  no security/tests) and `make verify-docs` (formatting only).

#### Governance — `.gitignore` and AGENTS.md

- **`.llm-sca/`** now fully ignored at any depth (replaces partial
  `blame/` + `manifests/` patterns); MCP workspace cache is reviewed as
  ephemeral generated state (HC2 allowlist note added).
- **AGENTS.md command allowlist** updated: all new `make verify-*` targets added;
  `detect-secrets scan --baseline` replaced with non-mutating form.
- **Verify-Before-Commit section** expanded with phase structure, `--frozen`
  notes, non-mutating secrets explanation, and scanner phase timeout table
  (soft: 10 min, hard: 15 min).

---

## [0.4.0] — 2026-05-19

### Changed

#### MCP server — upgrade to MCP protocol version 2025-11-25

- **Protocol version** bumped from `2024-11-05` to `2025-11-25`; server negotiates
  down to `2025-03-26` or `2024-11-05` if the client advertises an older version.
- **`ServerCapabilities` wire format** fixed: `resources`, `tools`, `prompts`, and
  `tasks` are now sent as objects (`{}`) as required by the spec, not booleans.
  Resolves the Codex / Claude Code handshake failure (`CustomResult` instead of
  `InitializedResult`).
- **`sampling`** removed from server capabilities — it is a client-only field.
- **`tasks`** promoted from `experimental` to a first-class `ServerCapabilities`
  field with `{"cancel": {}, "list": {}, "requests": {"tools": {"call": {}}}}`.
- **`initialize` params** — capabilities now read from `params.capabilities`
  (top-level, 2025-11-25 spec); legacy `params.clientInfo.capabilities` path
  kept as a fallback for older clients.

### Added

#### MCP server — standard `tasks/*` endpoints (2025-11-25)

- **`tasks/get`** — retrieve a single task by `taskId`.
- **`tasks/result`** — retrieve a task's result payload.
- **`tasks/cancel`** — cancel a running task (requires `enable_task_cancel`).
- **`tasks/list`** — list tasks with optional cursor-based pagination (requires
  `task_listing_allowed`).
- **`to_protocol_task()`** helper in `tasks.py` serialises `TaskRecord` to the
  2025-11-25 `Task` wire format (`taskId`, `createdAt`, `lastUpdatedAt`, `ttl`,
  `pollInterval` in ms; internal statuses `created/queued/running/cancelling`
  mapped to `working`; `expired` mapped to `failed`).

---

## [0.3.5] — 2026-05-19

### Fixed

#### MCP server — resolve impl-check clause evidence gaps

- **`get_relevant_files`** promoted from tier 3 to tier 1 so it appears in
  the default `tools/list` response without tier negotiation.
- **`resources/templates/list`** handler added to the stdio transport;
  previously returned `-32601 Method not found`.
- **`manifest-state` scanner** fixed to use `repo.root_path` instead of
  `hasattr(repo, "path")` fallback that always resolved to a non-existent
  path (RepositoryRecord has no `.path` attribute).
- **`impl_check_store`** added to `McpServerContext` as an in-process
  artifact store bridging `run_implementation_check` and resource handlers.
- **`artifact_sink` parameter** added to `run_implementation_check` so
  `matrix://`, `spec://`, `intent-graph://`, and `trace://` artifacts are
  captured after each run.
- **`run_implementation_check` tool handler** now persists a run record
  before/after execution and populates `impl_check_store` via `artifact_sink`.
- **Resource handlers** registered for `matrix://`, `spec://`,
  `intent-graph://`, and `trace://` URI schemes so post-run artifacts are
  readable via MCP resource reads.

---

## [0.3.4] — 2026-05-17

### Fixed

#### `setup` subcommand — exclude `agent.md` and `agents/` from Claude Code skills dir

- Skills were not visible in Claude Code because the skill directories
  contained `agent.md` and `agents/openai.yaml` (subagent / Codex metadata
  files) that do not belong in a Claude Code skill.  `shutil.copytree` was
  copying the entire source directory including those files.
- Added `_SKILL_COPY_EXCLUDES` and `_SKILL_COPY_EXCLUDES_CLAUDE` constants to
  drive a per-agent exclude set passed to `shutil.copytree(ignore=...)`.
- **Claude Code** skill dirs now contain only `SKILL.md` and standard
  subdirectories (`references/`, `scripts/`, `assets/`).
- **`~/.agents/skills/`** (Copilot CLI + Codex) keeps `agents/openai.yaml`
  for Codex UI metadata but still strips `agent.md`.
- Manually cleaned the three already-deployed skill dirs
  (`~/.claude/skills/{audit,fix,ship}/`) to remove the extraneous files.

---

## [0.3.3] — 2026-05-17

### Fixed

#### `setup` subcommand — correct skill paths for Codex CLI and Copilot CLI

- **Codex CLI skills**: corrected skill installation path from the previous
  (wrong) assumption that Codex has no skills to the correct
  `~/.agents/skills/` path, confirmed in the official Codex CLI documentation.
  Codex CLI fully supports the
  [Agent Skills open standard](https://agentskills.io).
- **GitHub Copilot CLI skills**: changed skill installation path from the
  invented `~/.copilot/skills/` to `~/.agents/skills/` — the Agent Skills
  standard user-level directory that both Copilot CLI and Codex CLI share.
  Skills are installed once to that shared location and both agents discover
  them automatically.
- **Codex `agents/openai.yaml`**: added `agents/openai.yaml` to each bundled
  skill directory. Codex uses this file for UI metadata (display name, short
  description, invocation policy) and tool dependency declarations in the
  Codex app and CLI plugin browser.

### Changed

#### `setup` subcommand — updated documentation

- Updated module-level docstring and CLI `--help` text to accurately describe
  which skill/MCP/agent paths are written for each AI agent:
  - Claude Code: `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude.json`
  - Copilot CLI: `~/.agents/skills/` (shared), `~/.copilot/agents/`, `~/.copilot/mcp-config.json`
  - Codex CLI: `~/.agents/skills/` (shared), `~/.codex/config.toml`

---

## [0.3.2] — 2026-05-17

### Changed

#### `setup` subcommand — agent detection before installation

- `setup` now detects which AI agents are installed before doing any work:
  - **Claude Code**: checks `shutil.which("claude")`
  - **GitHub Copilot CLI**: checks `shutil.which("gh")` then probes
    `gh copilot --version` (exit 0 = installed)
  - **Codex CLI**: checks `shutil.which("codex")`
- Prints a `FOUND` / `MISS` summary so the user knows exactly what was
  detected and what was skipped.
- Installs skills, sub-agents, and MCP **only for detected agents**.
- Added `--all` flag to bypass detection and configure all three agents
  regardless (useful in CI or when binaries are not on `PATH`).
- **Codex CLI**: correctly skips skills and sub-agents installation —
  Codex only supports MCP (`~/.codex/config.toml`); it has no skills
  or sub-agents directory.
- Removed the now-unnecessary `--skill-root` override option (was only
  needed because setup previously couldn't detect which agents existed).

---



### Fixed

#### `setup` subcommand — agent definition files now installed

- **Root cause**: `setup` previously only installed `SKILL.md` files to
  `~/.claude/skills/`, `~/.copilot/skills/`, `~/.codex/skills/`.  Claude Code
  and Copilot CLI require *separate* sub-agent definition files (different
  directory and naming convention) for agents to appear in `/agents`.
- Added `agent.md` bundled files for each skill (`audit`, `fix`, `ship`).
  Each file has YAML frontmatter with `name`, `description`, `skills:` (to
  preload the corresponding `SKILL.md` into the agent's context), and a concise
  workflow-routing body.
- `setup` now also writes:
  - `~/.claude/agents/<name>.md`        — Claude Code sub-agents
  - `~/.copilot/agents/<name>.agent.md` — GitHub Copilot CLI sub-agents
- Updated `--list` output to show agent file targets alongside skill dirs.
- After running `setup --force`, restart Claude Code and the agents will appear
  in `/agents` and via `/` slash-command routing.

---

## [0.3.0] — 2026-05-17

### Added

#### `setup` CLI subcommand
- New `llm-sca-tooling setup` command installs skills and configures the MCP
  server for all three supported AI agents in one step.
- Options: `--force` (overwrite existing), `--symlink` (symlink instead of
  copy), `--no-mcp` (skip MCP config), `--list` (dry-run list), `--skill-root`.
- Skill data (`audit/`, `fix/`, `ship/`) is now bundled inside the wheel under
  `src/llm_sca_tooling/skill_data/` and located at runtime via
  `importlib.resources`, so the command works from both an editable install and
  an installed wheel.
- MCP server is auto-configured in all three agent config locations:
  - **Claude Code** — `~/.claude.json` (`mcpServers.llm-sca-tooling`)
  - **Copilot CLI** — `~/.copilot/mcp-config.json` (`mcpServers.llm-sca-tooling`)
  - **Codex CLI** — `~/.codex/config.toml` (`[mcp_servers.llm-sca-tooling]`)
- Skills are installed to the per-agent skill directories:
  - `~/.claude/skills/`, `~/.copilot/skills/`, `~/.codex/skills/`

#### Consolidated skills (3 instead of 8)
The original 8 fine-grained skills were merged into 3 memorable, high-level
skills to reduce cognitive load for end users.

| New skill | Replaces |
|---|---|
| `audit` | `architecture-compliance`, `code-audit` |
| `fix` | `sast-repair`, `test-first-repair`, `safe-refactor` |
| `ship` | `dependency-update`, `evaluation`, `release` |

Each skill's `SKILL.md` includes a routing table so the agent selects the right
workflow automatically based on the user's request.

#### MCP tool tier filtering
Tools in the MCP server are now grouped into four tiers to control which tools
are visible by default:

| Tier | Count | Description |
|---|---|---|
| 1 | 8 | Primary workflow launchers (always visible) |
| 2 | 9 | Infrastructure / async-polling helpers |
| 3 | 13 | Evidence / query tools (internal plumbing) |
| 4 | 16 | Operational harness governance tools |

**Default** (`tools/list` with no special capabilities): **17 tools** (Tier 1 + 2).

To request the full surface of 47 tools, pass in the `initialize` request:
```json
{
  "clientInfo": {
    "capabilities": {"tool_tiers": [1, 2, 3, 4]}
  }
}
```

Implementation details:
- `ToolDescriptor` gained a `tier: int = 1` field.
- `ToolRegistry.list_descriptors_for_tiers(tiers)` filters by tier set.
- `MCPServer.initialize()` reads `tool_tiers` from `client_capabilities` and
  stores the negotiated set; `list_tools()` applies the filter.
- `stdio_transport.py` extracts `clientInfo.capabilities` (and top-level
  `capabilities`) from the MCP `initialize` frame and passes them to
  `server.initialize()`.

### Changed
- `pyproject.toml`: added `.agent/` to the `[tool.black]` exclude list to
  prevent Black from touching agent plan and lesson files.
- `evolve_static_rules` MCP tool is now **opt-in** via the
  `LLM_SCA_EVOLVE_RULES` environment variable (set to `1`, `true`, or `yes`).
  The tool is absent from `tools/list` by default even when Tier 4 is
  requested, because the architecture doc marks it "optional offline" (§2.1).
  Default `tools/list` with `tool_tiers: [1,2,3,4]` now returns **46 tools**;
  with `LLM_SCA_EVOLVE_RULES=1` it returns **47 tools**.

### Removed
- Old 8 skill directories from `.agents/skills/` and
  `src/llm_sca_tooling/skill_data/` (`architecture-compliance`, `code-audit`,
  `dependency-update`, `evaluation`, `release`, `safe-refactor`, `sast-repair`,
  `test-first-repair`).

---

## [0.2.0] — 2025 (prior releases)

See git log for earlier changes: `git log --oneline v0.2.0`.
