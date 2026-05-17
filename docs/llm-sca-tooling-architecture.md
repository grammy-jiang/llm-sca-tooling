# LLM-SCA Tooling Architecture

> **Date**: 2026-05-08 (updated for revision 6)
> **Derived from**: [[llm-based-static-code-analysis-research-report]] (§4 table totals: 126 full-PDF cards + 21 abstract-grade bridge cards + 16 unlocated stubs; 6 sub-areas + 7 gaps; revision 6 frames all sub-areas as six development directions, adds glue-script designs and closure protocols for all 7 gaps, expands §14 with a per-direction roadmap and self-evaluation harness, and extends Gap 4 (RDS) to v0.2 with a sixth `memorisation_distance` axis — bridged by `swe-bench-illusion`, `swe-qa-pro`, `livecoder`, and `swe-rebench-v2` (§13.4); Gap 4 remains the only academic-tagged open gap)
> **Harness-engineering overlay**: [[harness-engineering-for-local-coding-agents-research-report]] + [[harness-engineering-for-local-coding-agents-engineering-guide]]; incorporated where the ideas improve both the running tool/application and the way local AI agents develop it: live telemetry, run records, permission/tool governance, cost/context budgets, monitorable failure modes, reviewable memory promotion, stage-aware readiness scoring, manifest drift control, and continuous improvement from operational evidence.
> **Target languages**: C/C++, Python, JavaScript/TypeScript
> **Cross-language interfaces**: omniORB IDL (C/C++ ↔ Python), HTTP/REST + WebSockets (Python ↔ JS/TS); extensible via plugin system to gRPC/Protobuf and others

---

## Summary

This document is a **feature/function design document** for an LLM-based static code analysis tool. It describes what the tool should do, what evidence each function consumes and produces, and which research ideas justify each design choice. It intentionally avoids package layout, CLI syntax, persistence-table design, deployment, and other implementation details.

The product has two primary runtime artefacts, plus three mandatory governance surfaces:

1. **MCP Server — `code-intelligence`** — pre-built local index + MCP surface (Resources, Tools, Prompts, task-capable requests, Notifications/Subscriptions, and optional Sampling support) covering §7 A + §10 D, plus the SARIF/SAST loop (§13.7), typed graph schema (§13.3), and trajectory memory (§13.5)
2. **Skill — `code-audit`** — orchestration over the server (§6 control plane + §8 B + §9 C), exposing a small user-facing workflow surface while internally chaining investigation → repair → gates → evaluation, and with the §13.1 implementation-check DAG plus §13.2 patch-risk classifier integrated into the internal audit workflow
3. **Evaluation harness** — internal T1–T4 benchmark ladder from §14.3, using `swe-bench-live` as the headline suite, `swd-bench` for repo-QA, `swe-polybench`/`defects4c` for cross-language drift, and Vul4J/PoC⁺ data for implementation-check and patch-risk calibration
4. **Operational harness plane** — append-only session/run records, harness-condition sheets, permission/tool DAG enforcement, cost/context budgets, live monitors, incident records, manifest drift checks, stage-aware readiness reports, and reviewable promotion of lessons into memory or rules. This is the harness-engineering contribution: the tool must be diagnosable and improvable after real use, and the same controls must be available while local agents develop the package.
5. **Operational guardrails** — RDS v0.2 feature logging (§13.4), SARIF v2.1.0 as the analyser-data contract (§13.7), memory retention/eviction policy (§13.5), and trace/redaction policy for operational logs.

**Design review verdict:** the research-to-product mapping is strong, but the design must be read as a set of user-facing functions backed by structured evidence, not as a generic agent. The central product idea is: use a typed repository graph, analyser predicates, generated contracts, calibrated uncertainty, and contamination-aware evaluation to make LLM code analysis auditable.

**Core philosophy:**
- Cross-language and cross-repository scope is the **default**, not an option. Any investigation, call trace, or blast-radius analysis follows call chains through language boundaries (via interface plugins) and across repo boundaries automatically.
- The local pre-built index holds everything that changes only when code changes: typed graph edges, build/test evidence, SARIF alert streams, interface contracts, cached symbol summaries, and trajectory-memory records. Live LLM work happens only on top of this indexed, structured context.
- Cross-language interface types (IDL, HTTP/REST, WebSocket, and future ones like gRPC/Protobuf) are handled by a **plugin system**, so adding a new interface type requires writing a plugin, not modifying the core.
- The system does not ship on single-number resolve-rate. Every patch-review or implementation-check verdict is scored along functional, safety, uncertainty/calibration, cross-language compatibility, and contamination-controlled evaluation axes.
- The tool treats LLM output as a hypothesis. A verdict is trusted only when graph evidence, static-analysis evidence, contract evidence, tests/traces, or calibrated historical evidence support it.
- A "good" run is not only a correct answer. It is correct behaviour **and** maintainable structure **and** policy compliance **and** a traceable process. Every user-facing workflow must leave enough structured evidence for a reviewer to reconstruct what was asked, what context was used, which tools ran, which gates passed or failed, what was redacted, and why the final recommendation was made.

**User-facing interaction and citations:**
- User-facing agent interactions expose task names, not research machinery: developer workflows are `implementation-check`, `bug-resolve`, and optional `patch-review`; operator/reviewer workflows are `operational-review` and `readiness-audit`. Internal prompt names, paper names, benchmark names, and methodology labels are not shown unless the user asks for technical provenance.
- Design documents, detailed feature notes, ADRs, and evaluation reports **must** preserve citation traceability. Any non-trivial component derived from a paper-backed method must cite the relevant paper anchors from §6 and state how the idea is realised in `code-intelligence`, `code-audit`, or the evaluation harness.
- Feature/function definitions in this architecture carry local paper anchors beside the feature they justify. The registry in §6.1 resolves those anchors to full citation metadata; it is not a substitute for local traceability.
- Code comments and end-user output should not become citation-heavy. Citations belong at feature design boundaries, ADRs, and benchmark reports; user reports should focus on evidence, verdict, risk, and next action.

**Implementation mode tags used below:**
- `[PY-CODE]` — deterministic Python / normal programming implementation. This includes parsers, graph storage, schema validation, SARIF normalisation, tool wrappers, task state, cache invalidation, scoring formulas, and benchmark runners. These parts should have unit/integration tests.
- `[LLM]` — pure LLM reasoning or generation. This includes natural-language summaries, clause extraction drafts, candidate explanations, repair certificates, and review-agent analysis. These outputs are hypotheses unless checked by stronger evidence.
- `[HYBRID]` — Python orchestration plus LLM calls. The control flow, schemas, retries, provenance, validation, and gates are deterministic code; the ranking, explanation, synthesis, or judgement step uses an LLM.
- `[ML-MODEL]` — trained or calibrated non-deterministic model service invoked from Python, such as embeddings, path-retrieval models, and patch-risk classifiers. Treat like code at the interface level, but evaluate with held-out metrics and calibration checks.
- `[EVAL]` — deterministic evaluation / calibration harness. It may run LLM workflows as subjects under test, but the harness, metrics, splits, and gates are code.

Default rule for implementation planning: build `[PY-CODE]` evidence collection and validation first, then add `[LLM]` or `[ML-MODEL]` components behind typed interfaces. No `[LLM]` output should directly mutate code, mark a clause satisfied, or approve a patch without `[PY-CODE]` provenance and gates.

---

## Table of Contents

- [LLM-SCA Tooling Architecture](#llm-sca-tooling-architecture)
  - [Summary](#summary)
  - [Table of Contents](#table-of-contents)
  - [1. Six sub-areas mapped to daily-work tools](#1-six-sub-areas-mapped-to-daily-work-tools)
  - [2. MCP Server — `code-intelligence`](#2-mcp-server--code-intelligence)
    - [2.1 MCP Primitives: how each is used](#21-mcp-primitives-how-each-is-used)
      - [Resources (application-controlled, read-only data)](#resources-application-controlled-read-only-data)
      - [Tools (model-controlled, callable actions)](#tools-model-controlled-callable-actions)
      - [Prompt Templates (MCP prompts plus private workflow templates)](#prompt-templates-mcp-prompts-plus-private-workflow-templates)
      - [Async Tasks (long-running operations)](#async-tasks-long-running-operations)
      - [Notifications and Subscriptions (index freshness)](#notifications-and-subscriptions-index-freshness)
    - [2.2 Typed graph schema and evidence model](#22-typed-graph-schema-and-evidence-model)
    - [2.3 Intra-language indexing: existing tools as backends](#23-intra-language-indexing-existing-tools-as-backends)
    - [2.4 Cross-language interface plugin system](#24-cross-language-interface-plugin-system)
      - [Plugin contract](#plugin-contract)
      - [Built-in plugins](#built-in-plugins)
      - [Future plugins](#future-plugins)
    - [2.5 Multi-repository support](#25-multi-repository-support)
    - [2.6 Memory and experience replay](#26-memory-and-experience-replay)
    - [2.7 Operational harness and observability control plane](#27-operational-harness-and-observability-control-plane)
  - [3. Skill — `code-audit`](#3-skill--code-audit)
    - [3.1 User-facing workflows](#31-user-facing-workflows)
    - [3.2 Internal `investigate` mode](#32-internal-investigate-mode)
    - [3.3 Internal `repair` mode](#33-internal-repair-mode)
    - [3.4 Internal `audit` prompt mode](#34-internal-audit-prompt-mode)
  - [4. Feature and function design](#4-feature-and-function-design)
    - [4.1 End-to-end data flow](#41-end-to-end-data-flow)
    - [4.2 Shared evidence and verdict model](#42-shared-evidence-and-verdict-model)
    - [4.3 F1 — Repository intelligence graph](#43-f1--repository-intelligence-graph)
    - [4.4 F2 — Fault localisation and relevant-context discovery](#44-f2--fault-localisation-and-relevant-context-discovery)
    - [4.5 F3 — Repository question answering and behaviour tracing](#45-f3--repository-question-answering-and-behaviour-tracing)
    - [4.6 F4 — Implementation-check](#46-f4--implementation-check)
    - [4.7 F5 — Bug-resolve](#47-f5--bug-resolve)
    - [4.8 F6 — Patch-review and patch-risk classification](#48-f6--patch-review-and-patch-risk-classification)
    - [4.9 F7 — Static-analysis alert repair](#49-f7--static-analysis-alert-repair)
    - [4.10 F8 — Cross-language and cross-repository blast radius](#410-f8--cross-language-and-cross-repository-blast-radius)
    - [4.11 F9 — Dynamic trace augmentation](#411-f9--dynamic-trace-augmentation)
    - [4.12 F10 — Trajectory memory and experience replay](#412-f10--trajectory-memory-and-experience-replay)
    - [4.13 F11 — Operational harness, telemetry, and continuous improvement](#413-f11--operational-harness-telemetry-and-continuous-improvement)
    - [4.14 Feature interaction matrix](#414-feature-interaction-matrix)
    - [4.15 What the pre-built index saves](#415-what-the-pre-built-index-saves)
  - [5. Evaluation, scoring, and release gates](#5-evaluation-scoring-and-release-gates)
  - [6. Research paper anchors](#6-research-paper-anchors)
    - [6.1 Citation registry](#61-citation-registry)

---

## 1. Six sub-areas mapped to daily-work tools

The research report was organised into six sub-areas at the user's request. Each maps to a daily-work need:

| Sub-area | Daily-work need | Handled by | Implementation mode | Paper anchors |
|---|---|---|---|---|
| **§6 Control plane** (surveys, empirical anchors) | Repo-level issue-resolution harness — FL-conditioned repair, baseline comparison, and multi-axis scoring | `code-audit` issue-resolution controller + evaluation harness | `[HYBRID]` orchestration + `[EVAL]` gates | `survey-yang-2025`, `survey-issue-resolution-2026`, `agentless`, `fl-context-2026`, `swe-bench-live` |
| **§7 A** — Static FL & repo context | "Where is the bug? What code is relevant?" | `code-intelligence` MCP (static tools) | Mostly `[PY-CODE]`, with `[ML-MODEL]` retrieval and `[LLM]` explanations | `arise`, `locagent`, `cosil`, `repograph`, `codexgraph`, `rig` |
| **§8 B** — Execution-free / mostly-static repair | "Generate a fix" | `code-audit` skill, internal repair mode | `[HYBRID]`: `[LLM]` patch/spec generation + `[PY-CODE]` gates | `agentless`, `autocoderover`, `swe-fixer`, `specrover`, `agentic-code-reasoning`, `predicatefix` |
| **§9 C** — Spec, contracts, verification | "Does the implementation or fix match the design/spec?" | `code-audit` skill, internal repair + audit prompt modes | `[HYBRID]`: `[LLM]` interpretation + `[PY-CODE]` predicates/tests + `[ML-MODEL]` calibration | `codespecbench`, `kgacg`, `mids-valve`, `jml-autodoc`, `multi-agent-info-theory` |
| **§10 D** — Dynamic augmentation | "What's happening at runtime?" | `code-intelligence` MCP (live trace/debug tools) | `[PY-CODE]` trace capture + `[LLM]` compression/analysis | `trace-prompt`, `daira`, `tracerepair`, `inspectcoder` |
| **§11 E** — Benchmarks & evaluation | Multi-axis verdict: correctness + safety + drift; contamination-controlled release gates | Evaluation harness + internal audit workflow | `[EVAL]` deterministic harness | `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `swe-bench-illusion` |

**Consolidation logic:**
- A and D are both **infrastructure** → one MCP server
- B and C are both **workflows** consuming the infrastructure → one skill with internal modes
- §6 is the **control-plane workflow** over `investigate` → `repair` → deterministic gates → `evaluate`; §11 is **evaluation methodology** that shapes how release gates and implementation-check / patch-review verdicts are scored
- §13.2, §13.5, and §13.7 are **cross-cutting guardrails** — patch risk, memory/replay, and SAST-driven repair are integrated into the MCP server and invoked by the skill rather than exposed as separate standalone products
- §13.4 and §14.3 are **evaluation governance** — RDS v0.2 axes and the T1–T4 benchmark ladder are logged by the harness before any direction is declared production-ready

**Harness-engineering overlay:** the harness-engineering reports do not add another code-analysis algorithm. They add the product control plane that lets the tool run safely and improve from real usage:
- Observability is a first-class feature: every workflow emits cognitive, operational, and contextual trace events, because unsafe paths cannot be reconstructed reliably after the fact.
- Permission, tool, and path scope are runtime state, not prompt-only advice. Workflow stages expose only the tools needed for that stage.
- Cost, context, retries, and compaction are correctness concerns. Budget pressure and context loss become logged events that can change confidence or force human review.
- Memory promotion is reviewable. Raw sessions are evidence; only typed, validated, non-sensitive facts become durable memory or new rules.
- Recurrent incidents feed the product backlog through detectors, regression evals, readiness scores, and policy updates.
- Development-time harnessing is part of the design, not a separate process note. The repo being analysed or developed has a stage (`S0`-`S3`), an instruction/control-plane set (`AGENTS.md` as the canonical hard-constraint and project-policy file; `CLAUDE.md` importing `@AGENTS.md`; runtime overlays such as `.github/copilot-instructions.md` and `.codex/INSTRUCTIONS.md`; selected `SKILL.md` files; and the session plan), a drift state (`missing`, `stale`, `relaxed`, `out-of-stage`, `clean`), and an AI-readiness score that can block higher-autonomy workflows.

---

## 2. MCP Server — `code-intelligence`

A locally-running MCP server that maintains a pre-built index of all registered repositories and exposes structured code-intelligence to MCP-capable IDE, chat, and agent clients. The index lives alongside the repos, requires no external infrastructure, and is kept fresh as code changes.

**Cross-language and cross-repository scope is the default.** Every query follows call chains across language boundaries and repository boundaries automatically, using whichever interface plugins are registered. Scope narrowing is opt-in, not the other way around.

---

### 2.1 MCP Primitives: how each is used

The server uses the relevant MCP surfaces, with a clear control boundary:

- **Resources** are application-controlled context objects.
- **Tools** are model-controlled operations, including query, analysis, build, and long-running workflow launcher tools.
- **Prompts** are user-controlled templates exposed to clients; private decomposition prompts used by the skill are implementation templates, not required MCP prompt objects.
- **Tasks** are a protocol utility for long-running requests; they wrap tool calls or other task-capable requests but are not a separate user workflow.
- **Sampling** is client-provided LLM execution. The server may request it for review subagents only when the client advertises the capability and the user can approve it.

#### Resources (application-controlled, read-only data)

Resources expose the pre-built index as navigable, subscribable data sources. The MCP client (application layer) can read these directly and inject them into the LLM context without going through tool calls. Each resource has a URI; resources that are safe and useful to watch support `resources/subscribe` and update notifications.

**Mode mark:** resource plumbing, URI routing, schema validation, subscriptions, graph/SARIF/build/eval/memory reads, and freshness checks are `[PY-CODE]`. Cached symbol summaries and document-to-code bindings stored as resources are `[HYBRID]` because the cache/index mechanics are Python but the summary or binding text may be LLM-generated.

**Index resources:**
- `code-intelligence://repos` — list of registered repositories and their current index status. Paper anchors: `rig`, `logiclens`.
- `code-intelligence://schema/graph.schema.json` — versioned typed-edge schema used by every backend and plugin. Paper anchors: `rig`, `arise`, `repograph`, `codexgraph`, `logiclens`.
- `code-intelligence://schema/run-record.schema.json` — versioned operational event and run-record schema used for sessions, workflow tasks, gates, budgets, approvals, and incidents. Paper anchors: `agenttrace`, `aer`, `opendev`, `runtime-governance`.
- `code-intelligence://graph/{repo}` — the full call/import graph for a repo (or a multi-repo combined view). Paper anchors: `arise`, `locagent`, `cosil`, `repograph`, `codexgraph`, `repo-aware-kg`, `rig`.
- `code-intelligence://graph/slice/{repo}/{files}` — parameterised resource template: returns the subgraph (ego-network) for a given set of files, as a navigable JSON object. Paper anchors: `arise`, `locagent`, `repograph`, `codexgraph`.
- `code-intelligence://summary/{repo}/{symbol_path}` — LLM-generated natural-language summary of a symbol, cached against the current git hash; the resource updates (and notifies subscribers) whenever the file changes. Paper anchors: `reporepair`, `specrover`.
- `code-intelligence://blame/{repo}/{file_path}` — git blame chain for a file, including parent commit history. Paper anchors: `hafixagent`.
- `code-intelligence://build-evidence/{repo}` — RIG-style build/test evidence: components, package managers, runners, tests, and CI facts. Paper anchors: `rig`, `swe-polybench`.
- `code-intelligence://sarif/{repo}/{run_id}` — SARIF v2.1.0 alert stream from Semgrep, CodeQL, Bandit, SonarQube, or a project-specific analyser. Paper anchors: `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair`.
- `code-intelligence://eval/{run_id}` — benchmark-harness run metadata, suite freshness, sub-metrics, and RDS v0.2 feature logs. Paper anchors: `swe-bench-live`, `swd-bench`, `swe-polybench`, `swe-bench-illusion`, `swe-qa-pro`, `livecoder`, `swe-rebench-v2`.
- `code-intelligence://memory/{repo}/trajectories` — retained agent trajectories keyed by issue class, FL class, patch class, outcome, and utility score. Paper anchors: `agent-her`, `evo-memory`, `memory-management-empirical`, `graph-memory-rl`, `c2f-grounded-memory`.

**Interface plugin resources:**
- `code-intelligence://interfaces` — list of registered cross-language interface plugins and the interfaces they have indexed. Paper anchors: `rig`, `logiclens`, `eagle-x`.
- `code-intelligence://interfaces/{plugin_id}/{interface_name}` — the full interface contract as indexed by a given plugin (e.g., all methods of an IDL interface, or all HTTP routes under a path prefix), with both sides of the boundary linked. Paper anchors: `rig`, `logiclens`, `eagle-x`, `mids-valve`.

**Operational harness resources:**
- `code-intelligence://runs/{run_id}` — append-only workflow run record: user intent hash, workflow type, stage transitions, tool calls, approvals/denials, evidence IDs, budget events, compaction events, gate results, final verdict, and reviewer decision. Paper anchors: `agenttrace`, `aer`, `opendev`.
- `code-intelligence://runs/{run_id}/harness-condition` — harness-condition sheet for that run: model/backend, server/skill versions, exposed tool set, permission profile, sandbox/network policy, context policy, verification gates, telemetry/redaction policy, and recovery mode. Paper anchors: `harness-native-se`, `opendev`, `workstream`.
- `code-intelligence://operations/{repo}/ledger` — chronological operational ledger across runs: anomalies, blocked operations, budget overruns, repeated failures, incident links, memory promotions, and policy/ruleset changes. Paper anchors: `aer`, `cqa`, `agentic-harness-engineering`.
- `code-intelligence://governance/{repo}/policy` — effective permission/tool/path/data policy resolved from workspace defaults, repo configuration, workflow policy, and user-approved overrides. Paper anchors: `alara`, `runtime-governance`, `opendev`.
- `code-intelligence://governance/{repo}/manifest-state` — parsed instruction/control-plane state, hard constraints, runtime overlays, harness stage, drift findings, and whether overlays relax the `AGENTS.md` policy. Paper anchors: `opendev`, `tdad`, `agentic-harness-engineering`.
- `code-intelligence://readiness/{repo}` — repository AI-readiness and tool-readiness score across agent config, docs/spec coverage, CI/build evidence, code structure, security scanning, and available deterministic gates. Paper anchors: `workstream`, `needle-repo`.
- `code-intelligence://incidents/{incident_id}` — incident report for failures such as repeated-loop, out-of-scope write attempt, secret exposure, verification bypass, stale-index verdict, or budget exhaustion. Paper anchors: `agentfixer`, `aer`, `cqa`.

**Large-resource rule:** `code-intelligence://graph/{repo}` is a graph manifest plus chunk references, not an unconditional full-graph dump. Bounded work should use `code-intelligence://graph/slice/...` or `get_graph_slice(...)`, because full repo graphs can exceed client context, memory, and transport limits.

**Client subscription behaviour:** the client can subscribe to resources where the server declares support. When the server completes a `graph_update` from a file watcher, git hook, branch switch, or explicit user request, it emits `notifications/resources/updated` for affected graph, summary, SARIF, interface, eval, and memory resources. Clients refresh subscribed resources after notification rather than assuming an already-open copy is current.

---

#### Tools (model-controlled, callable actions)

Tools are query, analysis, build, and workflow operations that the LLM, skill, or client calls when more information is needed or when a long-running task must be started.

**Mode mark:** tool wrappers, argument validation, subprocess execution, graph queries, SARIF parsing, task state, and result schemas are `[PY-CODE]`. Tools that call LLMs for ranking, QA, synthesis, compression, or review are `[HYBRID]`; tools that invoke trained retrievers/classifiers are `[ML-MODEL]` behind Python interfaces.

**Query tools (read from pre-built index):**

**Mode mark:** `find_callers`, `find_callees`, `get_graph_slice`, `trace_cross_language`, `git_blame_chain`, and `get_interface_contract` are `[PY-CODE]`. `get_relevant_files` is `[ML-MODEL]` plus `[PY-CODE]` graph expansion. `classify_repo_question` and `answer_repo_question` are `[HYBRID]` / `[ML-MODEL]`, with `[PY-CODE]` provenance checks.

| Tool | Description | Scope | Paper anchors |
|---|---|---|---|
| `find_callers(symbol)` | Who calls this symbol? Follows cross-language interfaces automatically via all registered plugins | Cross-language, cross-repo by default | `arise`, `locagent`, `cosil`, `rig`, `logiclens` |
| `find_callees(symbol)` | What does this symbol call? Same cross-language traversal | Cross-language, cross-repo by default | `arise`, `locagent`, `cosil`, `rig`, `logiclens` |
| `get_relevant_files(issue_text)` | Semantic search: returns the most relevant files for a natural-language issue description, combining embedding similarity with graph-neighbour expansion | All registered repos | `fl-context-2026`, `rgfl`, `repo-aware-kg`, `repograph` |
| `get_graph_slice(files, edge_types?)` | Returns the typed ego-network of a given set of files, including call, import, data-flow, test, document, warning, and cross-language edges when requested | Cross-repo edges included | `arise`, `repograph`, `codexgraph`, `rig` |
| `trace_cross_language(start_symbol)` | Follows a call chain through all registered interface plugins in sequence; returns an ordered list of nodes across languages and repos | All plugins | `rig`, `logiclens`, `eagle-x`, `swe-polybench` |
| `git_blame_chain(file, line)` | Returns the blame chain for a specific location, including parent commits | Per-repo | `hafixagent` |
| `get_interface_contract(plugin_id, interface_name)` | Returns the full contract of a named interface as indexed by a plugin | Per-plugin | `rig`, `logiclens`, `mids-valve`, `jml-autodoc` |
| `classify_repo_question(question)` | Classifies a repo-QA request as `file-loc`, `behaviour-trace`, or `other`, so file-path retrieval and behaviour-tracing are evaluated under different accuracy regimes | All registered repos | `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa` |
| `answer_repo_question(question, repos?)` | Repo-level QA: routes `file-loc` questions through a `repo-path-retrieval-llm`-style service (≈91% EM when fine-tuned on AST-derived pairs), and behaviour-tracing questions through RepoChat-style NL→graph querying over the typed graph; returns provenance and a **confidence score**. `swd-bench` Functionality-Localization is the acceptance metric for file-loc; `swe-qa`/`coreqa` behaviour subsets are the ship-gate for behaviour-tracing | All registered repos | `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa`, `beyond-code-snippets` |
| `run_static_analysis(repo?, ruleset?)` | Runs Semgrep, CodeQL, Bandit, SonarQube, or a project-specific analyser; emits SARIF v2.1.0 with rule IDs, predicate IDs, locations, and alert provenance — feeds directly into `run_sast_repair` and patch-risk classification | Per-repo | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair` |
| `get_predicate_examples(predicate_id, corpus?)` | `predicatefix`-style bridging: negates the firing predicate, runs the analyser on a clean reference corpus, returns code snippets where the negated predicate fires — these contain the fix knowledge the LLM needs for that alert class; 27–69% more correct repairs than embedding-similarity RAG | Clean corpus (configurable) | `predicatefix` |
| `retrieve_memory(issue_text, phase)` | Retrieves coarse-to-fine experience records for similar issue, FL, or patch classes; filters out high-similarity/low-utility records per the §13.5 misalignment guard | All registered repos | `agent-her`, `evo-memory`, `memory-management-empirical`, `c2f-grounded-memory` |

**Analysis and verification tools (may read both index and live artefacts):**

**Mode mark:** `run_static_analysis`, `compute_rds_features`, `record_eval_result`, `record_trajectory`, and most SARIF/test/build comparisons are `[PY-CODE]`. `classify_patch_risk` is `[ML-MODEL]` plus `[PY-CODE]` calibration/gating. `run_sast_repair` and `evolve_static_rules` are `[HYBRID]` because patch/rule synthesis uses LLMs but validation and promotion are deterministic gates.

| Tool | Description | Paper anchors |
|---|---|---|
| `classify_patch_risk(diff, repo?)` | Gap 2 PR-time classifier: featurises AST diff + SARIF delta + graph slice + test residue, then returns `{safe, correct-but-overfit, vulnerable, vulnerability-introducing}` with calibrated probabilities; target macro-F1 ≥0.75 and ECE ≤0.10 before blocking merges | `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch`, `correct-not-safe`, `redteam-apr` |
| `run_sast_repair(alert_id, repo?)` | Gap 7 loop over a SARIF alert: alert → graph slice → PredicateFix/NullRepair/SecureFixAgent/CodeCureAgent-style repair → optional Agent-CoEvo regression tests → re-run SAST → build/test; emits patch plus SARIF delta | `predicatefix`, `nullrepair`, `securefixagent`, `codecureagent`, `agent-coevo` |
| `compute_rds_features(instance_or_issue)` | Computes RDS v0.2 feature vector: `files_touched`, `chain_depth`, `cross_file_dataflow`, `ambient_warning_load`, `test_brittleness`, and `memorisation_distance`; logs vector only until the cross-benchmark regression is published | `swe-bench-illusion`, `swe-qa-pro`, `livecoder`, `swe-rebench-v2`, `swe-polybench` |
| `record_eval_result(run_id, metrics)` | Stores T1–T4 harness outputs, suite freshness, contamination canaries, resolve-rate conditioned on FL, PoC⁺ pass-rate, and per-clause ECE | `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench`, `pvbench` |
| `record_trajectory(issue, decisions, patch, outcome)` | Stores success and failure trajectories for memory/replay; failed trajectories are eligible for Agent-HER-style goal relabelling before retrieval | `agent-her`, `graph-memory-rl`, `memory-management-empirical` |
| `evolve_static_rules(sarif_deltas, ruleset)` | Optional CodeQL-rule-multiagent loop; disabled by default unless it demonstrates ≥10 pp false-positive reduction at k=5 with zero true-positive loss | `codeql-rule-multiagent`, `predicatefix` |

**Operational harness tools (govern the running application):**

**Mode mark:** these tools are `[PY-CODE]` unless explicitly marked otherwise. They do not ask the LLM to police itself; they record, validate, block, compare, and promote operational evidence through deterministic schemas and policy checks.

| Tool | Description | Paper anchors |
|---|---|---|
| `record_run_event(run_id, event)` | Appends a typed event to the run record: stage transition, context load, tool call/result, approval, denial, diff snapshot, budget event, compaction, verification result, reviewer decision, or incident trigger | `agenttrace`, `aer`, `opendev` |
| `record_harness_condition(run_id, condition)` | Stores the exact runtime condition sheet for the workflow so benchmark and production outcomes are comparable across models, tool sets, policies, and context strategies | `harness-native-se`, `opendev`, `workstream` |
| `evaluate_tool_policy(action, stage, scope)` | Applies the effective permission/tool/path/data policy before an action runs; can allow, deny, require human approval, or narrow scope | `alara`, `runtime-governance`, `opendev` |
| `detect_run_anomalies(run_id)` | Detects repeated tool calls, repeated failing checks with no code change, context growth without new evidence, denied-operation storms, budget exhaustion, stale-index evidence, out-of-scope writes, and cumulative-risk patterns | `agenttrace`, `aer`, `cqa`, `agentfixer`, `agent-drift` |
| `compare_run_traces(run_a, run_b)` | Compares successful vs failed or previous vs current traces by stage, tool sequence, evidence deltas, policy events, cost, and verification results | `trace-level-comparison`, `aer`, `agentic-harness-engineering` |
| `assess_harness_stage(repo)` | Classifies the repository as `S0` greenfield, `S1` walking skeleton, `S2` growing, or `S3` production from code/test/CI/release/agent-config signals, then returns next-stage controls without skipping lower stages | `workstream`, `opendev`, `agentic-harness-engineering` |
| `classify_harness_drift(repo)` | Parses `AGENTS.md`, runtime overlays (`CLAUDE.md`, `.github/copilot-instructions.md`, `.codex/INSTRUCTIONS.md`), skills, tool descriptions, hooks, and CI policy; classifies each artefact as `missing`, `stale`, `relaxed`, `out-of-stage`, or `clean` | `tdad`, `opendev`, `agentic-harness-engineering` |
| `validate_harness_controls(repo)` | Runs manifest non-relaxation checks, readiness no-regression checks, prompt/tool-description regression tests, and required verify gates for the detected stage | `tdad`, `workstream`, `needle-repo` |
| `compute_readiness_score(repo)` | Scores whether a repository is ready for high-autonomy workflows across agent config, docs/spec links, CI/build reliability, code structure, security scanning, and deterministic gates | `workstream`, `needle-repo` |
| `run_maintainability_oracles(diff, repo?)` | Checks structural quality beyond tests: change locality, dependency direction, responsibility boundaries, reuse, testability, state ownership, and side-effect isolation | `needle-repo` |
| `run_prompt_manifest_regression(targets)` | Tests prompt-like artifacts and tool descriptions with visible/hidden behaviour checks, tool-order checks, policy mutation tests, and spec-evolution regressions | `tdad`, `opendev` |
| `promote_operational_lesson(source_run, target)` | Converts reviewed incidents or repeated successes into typed memory, a detector, a regression eval, a ruleset update, or a governance-policy change; rejects unreviewed prose memory | `schema-grounded-memory`, `ama-bench`, `agent-her`, `agentic-harness-engineering` |
| `record_incident(run_id, incident)` | Stores containment, impact, root cause, remediation, evidence links, detector/regression follow-up, and reviewer sign-off | `aer`, `agentfixer`, `cqa` |

**Build tools (modify the index; may be long-running — see Async Tasks below):**

**Mode mark:** all build/update/register/reload/compact mechanics are `[PY-CODE]`. `memory_compact` may use `[ML-MODEL]` utility scoring later, but the retention policy and final keep/drop decision should be deterministic and auditable.

| Tool | Description | Paper anchors |
|---|---|---|
| `graph_build(repo_paths)` | Full initial index build for one or more repos; runs all backend tools and populates the index | `rig`, `arise`, `repograph`, `codexgraph`, `logiclens` |
| `graph_update(repo_paths?, snapshot?)` | Incremental update: detects changed files via file watcher, `git diff`, or explicit worktree snapshot, then re-indexes affected nodes, summaries, SARIF bindings, and cross-language links | `rig`, `hafixagent` |
| `register_repo(repo_path)` | Add a new repo to the multi-repo workspace | `rig`, `logiclens` |
| `plugin_reload(plugin_id?)` | Re-run a specific interface plugin's indexing pass (e.g., after adding new IDL files) | `rig`, `logiclens`, `eagle-x` |
| `memory_compact(repo?)` | Applies Evo-Memory-style promote/demote/expire decisions to retained trajectories | `evo-memory`, `memory-management-empirical` |

**Workflow launcher tools (task-capable orchestration entry points):**

These tools exist so long-running user workflows can be represented as task-capable `tools/call` requests. The `code-audit` skill may call the lower-level tools directly, but clients that want a single server-owned operation can call these launchers.

**Mode mark:** workflow launchers are `[HYBRID]` at the top level. Their DAG execution, state machine, artefact storage, retries, budgets, and gates are `[PY-CODE]`; individual investigation, synthesis, QA, and review steps may be `[LLM]` or `[ML-MODEL]`.

| Tool | Description | Paper anchors |
|---|---|---|
| `run_implementation_check(spec, repos?, policy?)` | Executes the seven-stage design/spec → contract → graph → static/dynamic verdict → calibrated aggregation DAG and returns a clause verdict matrix | `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `codespecbench`, `swe-qa`, `coreqa` |
| `run_issue_resolution(issue_text, repos?, budget?)` | Executes investigate → repair → deterministic gates → patch-risk → blast-radius → trajectory recording | `agentless`, `fl-context-2026`, `rgfl`, `specrover`, `agent-coevo`, `swe-bench-live` |
| `run_patch_review(diff, context?, repos?, policy?)` | Executes multi-axis review, SARIF delta, patch-risk classification, contract compatibility, and behavioural-drift checks | `multi-agent-info-theory`, `correct-not-safe`, `compass`, `pvbench`, `logiceval`, `rig` |
| `run_eval_suite(suite, target?)` | Starts T1-T4 harness runs and records metrics, RDS v0.2 feature vectors, suite freshness, and contamination canaries | `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench`, `swe-bench-illusion` |
| `run_operational_review(run_id, policy?)` | Replays a run record and reports process compliance, trace completeness, denied/approved actions, budget behaviour, compaction loss, verification adequacy, maintainability-oracle results, and lessons eligible for promotion | `agenttrace`, `aer`, `runtime-governance`, `needle-repo`, `schema-grounded-memory` |
| `run_readiness_audit(repo, policy?)` | Scores the repository and tool configuration before higher-autonomy workflows, then returns harness stage, drift findings, missing gates, weak docs/spec links, unprotected risky paths, absent scanners, and recommended readiness tasks | `workstream`, `opendev`, `needle-repo` |

**Live tools (real-time, not cached):**

**Mode mark:** trace capture, process isolation, timeout handling, raw artefact storage, and redaction are `[PY-CODE]`. Trace summarisation/compression for LLM context is `[HYBRID]`.

| Tool | Description | Paper anchors |
|---|---|---|
| `capture_trace(script, scope_filter)` | Runs code with runtime trace hooks; the server LLM-compresses the raw trace before returning it; `scope_filter` prevents trace explosion | `trace-prompt`, `daira`, `tracerepair` |

---

#### Prompt Templates (MCP prompts plus private workflow templates)

MCP prompts are user-controlled templates that clients can list and explicitly select. They should expose the developer workflows and operator workflows, not every private reasoning substep. The `code-audit` skill may still keep private implementation templates such as `investigate`, `repair`, and `audit`, but those private templates are not required to appear in `prompts/list`.

**Mode mark:** prompt/template files and prompt selection are `[PY-CODE]` packaging/configuration; executing the prompt content is `[LLM]` or `[HYBRID]` depending on whether tools/gates are called.

Prompt retrieval (`prompts/get`) returns structured instructions, resource references, and suggested tool calls; it does not itself execute a long-running analysis. Long-running execution is launched through task-capable tools such as `run_issue_resolution`, `run_implementation_check`, `run_patch_review`, `run_operational_review`, `run_readiness_audit`, and `run_eval_suite`.

| Prompt / template | Visibility | Arguments | What it assembles | Paper anchors |
|---|---|---|---|---|
| `implementation-check` | Public MCP prompt | `spec`, `repos?`, `policy?` | User-facing instructions and resource/tool plan for `run_implementation_check`; hides paper names and internal stage labels unless provenance is requested | `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `codespecbench` |
| `bug-resolve` | Public MCP prompt | `issue_text`, `repos?`, `budget?` | User-facing instructions and resource/tool plan for `run_issue_resolution`; maps to private `investigate` → `repair` → gates → `blast-radius` templates | `agentless`, `fl-context-2026`, `rgfl`, `specrover`, `swe-bench-live` |
| `patch-review` | Public MCP prompt | `diff`, `context?`, `repos?`, `policy?` | User-facing instructions and resource/tool plan for `run_patch_review`; includes SARIF, contract, patch-risk, behavioural-drift, and compatibility gates | `multi-agent-info-theory`, `correct-not-safe`, `compass`, `pvbench`, `rig` |
| `operational-review` | Public/operator MCP prompt | `run_id`, `policy?` | Reconstructs a completed or failed run from structured events, checks process compliance, surfaces anomalies, and proposes reviewed lessons for memory/eval/policy promotion | `agenttrace`, `aer`, `runtime-governance`, `schema-grounded-memory` |
| `readiness-audit` | Public/operator MCP prompt | `repo`, `policy?` | Scores repository/tool readiness, reports harness stage and drift, and returns the missing operational controls that make high-autonomy analysis risky | `workstream`, `opendev`, `needle-repo` |
| `investigate` | Private skill template | `issue_text`, `repos?` | Loads relevant graph slices and summaries as resource context, then structures the reasoning chain for fault localisation | `fl-context-2026`, `rgfl`, `arise`, `locagent`, `cosil` |
| `repair` | Private skill template | `location`, `issue_context?` | Loads the graph slice for the fault location plus any cross-language interface contracts that the symbol participates in, then templates the patch + spec workflow | `specrover`, `agentic-code-reasoning`, `agent-coevo`, `predicatefix` |
| `audit` | Private skill template | `content`, `mode: patch\|implementation_check` | Templates the adapted 4-agent parallel check plus patch-risk/SARIF gates (for patches) or the seven-stage design/spec → implementation-check DAG for implementation compliance | `multi-agent-info-theory`, `correct-not-safe`, `kgacg`, `mids-valve`, `jml-autodoc`, `codespecbench` |
| `blast-radius` | Private skill template | `change_set`, `repos?` | Loads graph slices for all changed symbols and traces outward through callers and interface boundaries; returns an impact map | `arise`, `rig`, `logiclens`, `swe-polybench` |
| `sast-repair` | Private skill template | `alert_id`, `repo?` | Gap 7 SARIF loop: alert → predicate and SARIF context → predicate examples → graph slice → patch → coevolved checks → static analysis/build/test re-check | `predicatefix`, `nullrepair`, `securefixagent`, `codecureagent`, `agent-coevo` |
| `risk-classify` | Private skill template | `diff`, `repo?` | Runs the Gap 2 classifier and emits risk class, calibrated probability, feature evidence, and merge/block recommendation | `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch`, `correct-not-safe` |
| `evaluate` | Private skill template | `suite: T1\|T2\|T3\|T4`, `target?` | Starts the internal evaluation harness via `run_eval_suite` and logs resolve-rate, FL-conditioned repair rate, PoC⁺ pass-rate, repo-QA accuracy, cross-language drift, RDS v0.2 features, and contamination canaries | `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench`, `swe-bench-illusion` |

---

#### Async Tasks (long-running operations)

Operations that take more than a few seconds — `graph_build`, `graph_update`, `run_static_analysis`, `run_sast_repair`, `classify_patch_risk` over large diffs, `capture_trace`, `run_issue_resolution`, `run_implementation_check`, `run_patch_review`, `run_operational_review`, `run_readiness_audit`, and T1-T4 evaluation suites — are represented as MCP task-augmented requests following the 2025-11-25 Tasks primitive (SEP-1686 call-now / fetch-later pattern, currently experimental):

**Mode mark:** task lifecycle, persistence, polling, cancellation, progress events, TTL, and authorization binding are `[PY-CODE]`.
- The server declares `tasks.requests.tools.call`; if supported, it also declares `tasks.list` and `tasks.cancel` so clients can inspect and stop long-running jobs.
- Long-running tools declare `execution.taskSupport: "optional"` or `"required"` in `tools/list`; clients must not assume all tools are task-capable just because the server supports tasks.
- A task-capable request includes `params.task` with the requested `ttl`. The receiver accepts the request and immediately returns a `CreateTaskResult` with a receiver-generated `taskId`, `status`, `ttl`, and suggested `pollInterval`.
- The client polls `tasks/get`, may call `tasks/cancel`, and retrieves the completed operation result with `tasks/result`. `tasks/list` is used by clients to recover visible job state after restart.
- The server may emit `notifications/tasks/status` and progress notifications over Streamable HTTP as stages complete (e.g., "ctags complete", "IDL plugin: 42 interfaces indexed", "SARIF: 131 alerts normalised", "RDS: memorisation-distance probe done", "embeddings: 1200/3400 nodes", "policy: approval required for execute", "budget: 85% context used", "monitor: repeated failing gate detected"), but clients must keep polling and must not rely on notifications alone.
- Task IDs are treated as sensitive capabilities. If the transport has authorization, task state and results are bound to that authorization context; in local unauthenticated transports, task IDs must be high-entropy, TTLs must be bounded, and `tasks.list` should be disabled unless the server is single-user.
- Because the Tasks primitive is still experimental, the feature design treats tasks as a conceptual long-running job model. Protocol field changes should not alter the user-visible behaviour: start work, show progress, support cancellation, and retrieve the result later.

---

#### Notifications and Subscriptions (index freshness)

- File watchers, explicit user requests, and git hooks call `graph_update` for both committed and uncommitted worktree snapshots; the server sends `notifications/resources/updated` for all affected resources
- `notifications/resources/list_changed` fires when a new plugin is registered or a new repo is added, so clients refresh their resource lists
- SARIF, eval, and memory changes are surfaced through standard `notifications/resources/updated` on `code-intelligence://sarif/...`, `code-intelligence://eval/...`, and `code-intelligence://memory/...`; optional server-specific notifications such as `notifications/sarif/updated` are advisory only
- Run records, readiness scores, policy changes, and incident records are surfaced through standard `notifications/resources/updated` on `code-intelligence://runs/...`, `code-intelligence://readiness/...`, `code-intelligence://governance/...`, and `code-intelligence://incidents/...`
- Budget and monitor notifications are advisory but must also be persisted as run events. A client that misses a live "budget near hard limit" or "doom-loop candidate" notification can recover the same state from the run record.
- Clients that have graph resources open refresh on notification and must include the `git_sha` / `worktree_snapshot_id` they used in every verdict, so stale-index uncertainty is visible

---

### 2.2 Typed graph schema and evidence model

The index is governed by a checked-in, versioned `graph.schema.json`. This is the §13.3 cross-language contract: language backends and interface plugins may use different native parsers, but they all emit the same typed nodes, edges, and provenance records.

**Mode mark:** schema definitions, validation, provenance records, snapshot IDs, edge confidence, and graph persistence are `[PY-CODE]`. LLM-derived edges may be produced by `[LLM]`, but accepting, storing, and downgrading their confidence is deterministic `[PY-CODE]`.

**Node types:**

| Node type | Examples |
|---|---|
| Repository structure | `repo`, `package`, `directory`, `file`, `module` |
| Code symbols | `class`, `function`, `method`, `variable`, `type`, `interface` |
| Interface boundary | `idl_interface`, `http_route`, `websocket_event`, `grpc_service`, `protobuf_message` |
| Specification and contracts | `document`, `design_clause`, `intent_node`, `contract_artifact`, `generated_test`, `predicate` |
| Evidence | `test`, `runtime_trace`, `sast_rule`, `sarif_alert`, `build_target`, `ci_job`, `eval_run` |
| Change and review | `patch`, `diff_hunk`, `risk_finding`, `verdict` |
| Agent memory | `trajectory`, `issue_class`, `fl_decision`, `patch_class`, `outcome` |
| Operational harness | `session`, `run_record`, `run_event`, `harness_condition`, `permission_profile`, `tool_policy`, `tool_call`, `approval`, `budget_event`, `compaction_event`, `monitor_alert`, `incident`, `readiness_score`, `maintainability_oracle`, `manifest_regression` |

**Minimum edge types:**

| Edge type | Semantics | Main provenance | Paper anchors |
|---|---|---|---|
| `contains` | repo/package/file owns a child node | file tree, parser | `arise`, `repograph`, `codexgraph`, `rig` |
| `imports` | module/package dependency | language-native import/package metadata | `arise`, `repograph`, `rig` |
| `calls` | symbol A invokes symbol B | libclang, pyan3, ts-morph, CodeQL, LSP | `arise`, `locagent`, `cosil`, `marscode` |
| `dataflow` | value computed in A reaches B | CodeQL, Semgrep taint, language data-flow backend | `arise`, `rig`, `codexgraph` |
| `tests` | test exercises a symbol or route | RIG/SPADE build-test evidence, coverage, naming heuristics | `rig`, `swe-polybench`, `agent-coevo` |
| `documents` | design/spec/doc section claims to describe a symbol | doc parser + graph binding | `reporepair`, `kgacg`, `mids-valve`, `swd-bench` |
| `decomposes_to` | document/spec section becomes an atomic design clause or intent node | intent parser | `kgacg`, `mids-valve` |
| `checks` | generated predicate, test, JML-like contract, or CodeQL/Semgrep rule checks a clause or symbol | contract generator, analyser | `jml-autodoc`, `predicatefix`, `codespecbench` |
| `satisfies` / `violates` | evidence supports or contradicts a design clause, contract, or patch claim | static/dynamic verdicts, aggregator | `codespecbench`, `agent-coevo`, `why-llms-fail-secpatch` |
| `implements` | concrete code implements an abstract interface | IDL/proto/HTTP/WebSocket plugins | `rig`, `logiclens`, `mids-valve` |
| `exposes` / `consumes` | server exposes and client consumes an interface | interface plugins | `rig`, `logiclens`, `eagle-x` |
| `ffi` | foreign-function or cross-language boundary | RIG annotations, IDL/proto plugins, parser extern nodes | `rig`, `swe-polybench`, `eagle-x` |
| `nullable` | nullness or optionality contract | CodeQL, NullAway-style rules, type system | `nullrepair`, `jml-autodoc` |
| `owns` | ownership / move semantics | Rust future plugin, C++ smart-pointer rules | `swe-polybench`, `defects4c` |
| `instantiates` | template/generic instantiation | clangd/libclang, future Java JDT backend | `swe-polybench`, `defects4c`, `marscode` |
| `warned_by` | SAST alert fires on a node | SARIF v2.1.0 | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair` |
| `fixed_by` | patch or trajectory resolved an alert/issue | repair loop output | `agent-her`, `evo-memory`, `graph-memory-rl`, `codecureagent` |
| `changed_by` | patch hunk changes a node, edge, or interface contract | diff parser, AST diff | `compass`, `pvbench` |
| `observed_in` | runtime trace, failing test, or PoC observes a symbol/path/state | trace/test harness | `trace-prompt`, `daira`, `tracerepair`, `agent-coevo` |
| `used_tool` | run or stage invoked a tool with validated arguments and policy outcome | run-event logger | `agenttrace`, `opendev`, `runtime-governance` |
| `approved_by` / `denied_by` | action was approved or denied by policy or human reviewer | policy engine, approval event | `runtime-governance`, `alara`, `aer` |
| `verified_by` / `blocked_by` | patch, verdict, or workflow was accepted or blocked by a gate, monitor, or reviewer | verification harness, monitor, review decision | `saver`, `severa`, `needle-repo`, `aer` |
| `compacted_to` | large context or trace was reduced into a checkpoint or summary with a source artefact link | context manager | `tokalator`, `opendev` |
| `promoted_to` | reviewed run evidence became durable memory, a detector, a ruleset/policy change, or an eval regression | memory/governance promotion tool | `schema-grounded-memory`, `agent-her`, `agentic-harness-engineering` |
| `triggered_incident` | monitor alert or reviewer decision opened an incident record | monitor, incident recorder | `agentfixer`, `cqa`, `aer` |

Each node and edge carries `{source_tool, source_version, repo, git_sha, worktree_snapshot_id?, file?, span?, confidence, derivation: parser|analyser|build|test|trace|llm|heuristic|policy|review}` where the file/span fields are optional for operational events. Low-confidence or LLM-derived edges are never silently treated as hard facts; downstream prompts must show uncertainty or require static verification.

**Contract artefact schema:** any `contract_artifact` produced by implementation-check or repair must carry `{clause_id, language, artifact_type: jml|codeql|semgrep|pytest|unit_test|natural_language_probe, target_symbols[], source_clause_span, compile_status, last_run_status, confidence}`. This is the hand-off format between the design/spec pipeline (§13.1), SARIF repair (§13.7), and patch review (§13.2).

**Patch and verdict schema:** any `patch`, `risk_finding`, or `verdict` node must carry `{diff_id, changed_symbols[], sarif_delta_id?, test_delta_id?, risk_class?, calibrated_probability?, ece_bucket?, policy_action}`. This keeps "passed tests", "no new warnings", and "safe to merge" as separate claims rather than one collapsed status.

**Run-record schema:** any `run_record` node must carry `{run_id, workflow, user_intent_hash, repos[], start_ts, end_ts?, status, model_backend, toolset_hash, policy_id, permission_profile, context_budget, run_event_count, harness_condition_id, final_verdict_id?, incident_ids[], redaction_policy}`. `run_event` nodes carry `{event_id, run_id, seq, ts, type, actor, stage, input_ref?, output_ref?, policy_action?, token_count?, wall_ms?, artefact_ids[], redaction_status}`. This is the operational substrate for review, replay, budget analysis, incident response, and memory promotion.

**Evidence retention:** the graph is a local evidence model, not a remote service dependency. It retains graph facts, SARIF facts, evaluation facts, memory records, summaries, embeddings, and large graph slices with provenance and freshness metadata so every downstream verdict can cite the version of evidence it used.

---

### 2.3 Intra-language indexing: existing tools as backends

No custom parsers are written. Each language backend is an existing tool; the server is the glue that imports their output into the index.

**Mode mark:** backend invocation, output parsing, graph normalisation, cache invalidation, and error handling are `[PY-CODE]`. LLM-generated symbol summaries are `[HYBRID]` and must never replace parser/analyser facts.

| Language | Tool | What it provides | Paper anchors |
|---|---|---|---|
| All languages | `tree-sitter` | AST nodes and language-normalised syntax facts for `graph.schema.json` | `arise`, `locagent`, `repograph`, `codexgraph` |
| All languages | `universal-ctags` | Symbol definitions (functions, classes, methods, variables) | `arise`, `repograph`, `rig` |
| All languages with mature servers | LSP adapters (`clangd`, Pyright/Pylance, `tsserver`, JDT) | go-to-definition, references, diagnostics, rename/ABI-sensitive symbol facts; used as a cross-check against parser-derived edges | `marscode`, `rig`, `swe-polybench` |
| All / build evidence | RIG/SPADE-style extractor + build-system plugins | Components, package managers, runners, tests, build targets, and external packages; C/C++ can use CMake File API + CTest immediately, with npm/pytest adapters for JS/TS and Python | `rig`, `swe-polybench` |
| C/C++ | `libclang`/`clangd` Python bindings + `bear` for `compile_commands.json` | Call graph, inheritance edges, template instantiations, ABI-relevant signatures | `marscode`, `defects4c`, `swe-polybench` |
| Python | `pyan3` | Call and import graph | `arise`, `locagent`, `swe-bench-live` |
| JS/TS | `ts-morph` (TypeScript compiler API) or `madge` | Call and import graph | `swe-polybench`, `rig` |
| Java (optional, for Vul4J / SWE-PolyBench parity) | JDT / CodeQL Java | Symbol, call, generic-instantiation, and nullness edges when Java projects enter the benchmark or customer corpus | `swe-polybench`, `nullrepair`, `jml-autodoc` |
| All | `semgrep` with custom rule files | HTTP route and WebSocket event detection; **predicate-driven static-analysis alerting** (`predicatefix` pattern: run Semgrep rules to find alerts, then negate rule predicates on a clean corpus to retrieve fix-knowledge examples); output normalised to SARIF | `predicatefix`, `codecureagent`, `securefixagent` |
| All (optional) | `codeql` (if installed) | Datalog-style predicate queries over the code graph; stronger than Semgrep for interprocedural taint/control-flow properties; output feeds the same `run_static_analysis` tool as SARIF | `predicatefix`, `codeql-rule-multiagent`, `logiceval` |
| Python security (optional) | `bandit` | Python-specific SAST alerts normalised to SARIF | `securefixagent`, `why-llms-fail-secpatch` |
| Enterprise SAST (optional) | SonarQube / GitHub Advanced Security import | External warning stream normalised to SARIF v2.1.0 and bound to graph nodes | `codecureagent`, `securefixagent`, `predicatefix` |
| Git | `git log` + `git blame` | Blame chains and commit history | `hafixagent` |
| Embeddings | Any embedding API | Per-symbol semantic vectors (cached, invalidated on git hash change) | `fl-context-2026`, `repo-aware-kg`, `reporepair` |

LLM-generated natural-language summaries are computed lazily: generated on first access for a symbol and cached until the symbol's file changes.

---

### 2.4 Cross-language interface plugin system

Cross-language boundaries are handled by an extensible plugin system. Each plugin knows about one type of interface (IDL, HTTP/REST, WebSocket, gRPC, …) and implements the same plugin contract. The core server has no hard-coded knowledge of any specific interface type — all such knowledge lives in plugins. Plugins emit normal graph nodes and edges (`implements`, `exposes`, `consumes`, `ffi`, `dataflow`) into `graph.schema.json`; cross-language support is therefore part of the graph contract, not a special retrieval path.

**Mode mark:** plugin detection/parsing/linking/traversal is `[PY-CODE]`. LLM assistance may be used only as `[HYBRID]` fallback for ambiguous schema or route descriptions, and ambiguous links must remain low-confidence candidates until code evidence confirms them.

#### Plugin contract

Each plugin provides:

1. **Detect** — given a list of repo paths, identify which files or code patterns constitute interface definitions for this interface type (e.g., `.idl` files, FastAPI route decorators, `.proto` files). Paper anchors: `rig`, `logiclens`.
2. **Index** — parse the interface definitions and extract the interface contract: named operations/endpoints/events, parameter types, return types, nullability/ownership hints when available, and the language on each side of the boundary. Paper anchors: `rig`, `mids-valve`, `jml-autodoc`.
3. **Link** — connect the abstract interface contract to concrete code nodes in the intra-language graph (e.g., link an IDL method to its C++ servant implementation and to its Python client caller), emitting typed graph edges with provenance. Paper anchors: `rig`, `logiclens`, `eagle-x`.
4. **Traverse** — given a node on one side of the boundary, return the set of nodes on the other side that are reachable through this interface; this is what `trace_cross_language` calls at each boundary hop. Paper anchors: `arise`, `rig`, `logiclens`, `swe-polybench`.

Plugins register their capabilities with the server. Adding a new interface type should extend the plugin capability set without changing the core graph contract.

Every plugin emits the same `InterfaceRecord` shape:

| Field | Meaning |
|---|---|
| `interface_id` | Stable ID derived from interface definition, operation, version, and repo |
| `kind` | `idl`, `http`, `websocket`, `grpc`, `protobuf`, or plugin-defined extension |
| `operation` | Method, route, event, RPC, or message name |
| `canonical_signature` | Normalised parameters, return type, nullability, error channel, and payload schema where known |
| `producer_nodes` / `consumer_nodes` | Concrete code nodes linked to each side of the boundary |
| `generated_artifacts` | Generated stubs/skeletons, OpenAPI/proto outputs, or IDL compiler outputs when present |
| `confidence` | Exact, inferred, or ambiguous link confidence with provenance |

Interface links are never all-or-nothing. If a plugin can detect a route/event but cannot prove a client/server match, it emits candidate `exposes` / `consumes` edges with low confidence and a reason. F8 blast-radius and F6 patch-review then surface those candidates instead of silently treating them as confirmed downstream impact.

#### Built-in plugins

| Plugin | Interface type | Server-side languages | Client-side languages | Paper anchors |
|---|---|---|---|---|
| `omniORB-IDL` | omniORB IDL (`.idl` files) | C/C++ (POA skeleton + servant implementation) | Python (generated `*_idl.py` stubs and their callers) | `rig`, `logiclens`, `defects4c` |
| `HTTP-REST` | HTTP/REST APIs | Python (FastAPI / Flask / Django route handlers) | JavaScript/TypeScript (fetch, axios, other HTTP clients) | `rig`, `logiclens`, `swe-polybench` |
| `WebSocket` | WebSocket events | Python (socket.io server, `@socketio.on` handlers) | JavaScript/TypeScript (socket.io client, `socket.emit` / `socket.on`) | `rig`, `logiclens`, `swe-polybench` |

**How `omniORB-IDL` plugin works (example):** the plugin uses `omniidl -p` to dump the IDL file's AST, extracts interface names and method signatures, then finds the C++ POA skeleton classes and servant implementations via `libclang`, and finds the Python stub modules and their callers via `pyan3`. All four sides (IDL definition → C++ impl → Python stub → Python callers) are linked into a single interface record in the index.

**How `HTTP-REST` plugin works (example):** the plugin first consumes OpenAPI/Swagger documents when available. If no schema exists, it uses `semgrep` rules and framework adapters to detect route decorators in Python server code and HTTP client calls in JS/TS code, normalises URL path patterns to a canonical form for matching (handling `/users/:id`, `/users/{id}`, `/users/<id>` equivalently), and links matched server-side handler nodes to client-side call-site nodes. It records method, path, request/response schema, status-code contract, auth hints, and confidence.

**How `WebSocket` plugin works (example):** the plugin detects event registration and emission sites, extracts event names plus payload-shape hints from TypeScript types, Pydantic/dataclass models, JSON-schema literals, or nearby validation code, and links listeners to emitters by event name and namespace. Dynamic event names are emitted as low-confidence candidates unless a finite set can be statically resolved.

#### Future plugins

The plugin contract is designed to accommodate any binary or message-based interface:

| Planned plugin | Interface type |
|---|---|
| `gRPC` | gRPC services (`.proto` files, generated stubs) |
| `Protobuf` | Protocol Buffer serialization boundaries |
| `ZeroMQ` | ZeroMQ socket patterns |
| `MQTT` | MQTT topic-based publish/subscribe |
| `DBUS` | D-Bus service interfaces |

Adding any of these is a self-contained plugin — no changes to the core server or to existing plugins.

---

### 2.5 Multi-repository support

The server maintains a workspace of registered repositories, all indexed into a shared graph. All tools and resources operate across all registered repos by default:

**Mode mark:** repo registration, cross-repo graph overlays, scope filters, and traversal limits are `[PY-CODE]`.

- `find_callers` returns callers in all repos (filtered by plugin-traversed cross-language edges between repos, if applicable)
- `trace_cross_language` follows chains across repo boundaries wherever a cross-repo interface link exists (e.g., a Python service in repo A calling a C++ service in repo B via IDL)
- `get_relevant_files` searches all repos simultaneously
- The `blast-radius` template maps impact across all repos in one operation

Scope narrowing to a single repo or language is supported as an optional argument on all tools, but is not the default.

---

### 2.6 Memory and experience replay

The memory layer is not a separate product. It is an indexed resource inside `code-intelligence` and a retrieval step inside `code-audit`, implementing the §13.5 glue design.

**Mode mark:** memory persistence, redaction, retention, retrieval filters, and opt-in policy are `[PY-CODE]`. Similarity/utility scoring can be `[ML-MODEL]`; hindsight relabelling of failed trajectories is `[LLM]` but must be stored as a labelled hypothesis.

| Concern | Architecture decision | Paper anchors |
|---|---|---|
| Storage | Persist every meaningful trajectory as `{issue, repo, FL_decisions[], graph_slices[], patch, SARIF_delta, tests, outcome, utility}` and link it to graph nodes via `fixed_by` / `warned_by` / `documents` edges | `graph-memory-rl`, `agent-her` |
| Failure reuse | Failed trajectories are not discarded; Agent-HER-style relabelling can convert a failed goal-A trajectory into a useful demonstration for a sibling goal B | `agent-her` |
| Eviction | `memory_compact` applies Evo-Memory-style promote/demote/expire decisions using utility, recency, issue-class coverage, and outcome diversity | `evo-memory`, `memory-management-empirical` |
| Misalignment guard | Retrieval rejects records that are high-similarity but historically low-utility, addressing error propagation and misaligned experience replay | `memory-management-empirical` |
| Retrieval shape | Coarse retrieval happens during investigation (issue-class and FL-class); fine retrieval happens during repair and internal audit workflows (concrete edit, predicate, test, or risk-pattern hints) | `c2f-grounded-memory`, `reporepair`, `predicatefix` |
| Schema-grounded facts | Exact project facts, decisions, constraints, incidents, allowed commands, and component ownership are stored as validated records with explicit unknowns and source links, not as prose memory | `schema-grounded-memory`, `ama-bench` |

**Privacy and retention:** trajectory memory is opt-in per workspace. It stores structured decisions, graph node IDs, hashes, SARIF/test deltas, incidents, reviewer decisions, and bounded snippets rather than raw prompts or full source files by default. Secret scanning and PII redaction run before persistence, and every memory record carries retention class, expiry, source run, owner, export/delete metadata, and rollback path.

**Promotion rule:** operational evidence is not memory until reviewed. `promote_operational_lesson` can promote a run lesson only if it has a concrete trigger, structured fields, enforcement/check path, source links, expiry or review date, and a rollback path. Otherwise it remains an artefact in the run ledger.

**Ship gate:** HER + eviction must beat success-only memory by ≥3 pp pass-rate at constant context budget on the internal T2/T3 harness before memory hints are enabled by default.

---

### 2.7 Operational harness and observability control plane

The operational harness plane makes the tool itself reviewable. It is not a separate developer-process document; it is runtime product functionality inside `code-intelligence` and `code-audit`. Every long-running workflow has a run record, a harness-condition sheet, a policy profile, budget state, monitor events, and promotion hooks for turning reviewed operational evidence into better rules, evals, or memory.

**Mode mark:** event capture, policy evaluation, budget accounting, compaction, anomaly detection, incident records, readiness scoring, and promotion gates are `[PY-CODE]`. Optional narrative summaries for reviewers are `[LLM]`, but the stored facts and blocking decisions are deterministic.

**Run-record event classes:**

| Event class | Examples | Product use |
|---|---|---|
| Cognitive trace | intent parse, plan, hypothesis, candidate ranking, certificate, uncertainty note | Lets reviewers see why a verdict was reached without trusting an unstructured transcript |
| Operational trace | tool call/result, task start/end, retry, cancellation, approval/denial, diff snapshot, gate result | Reconstructs what the tool did and whether it followed the allowed workflow |
| Context trace | resources loaded, graph snapshot IDs, summaries used, token counts, compaction/checkpoint events, redaction decisions | Makes stale context, context loss, and budget pressure visible |
| Governance trace | effective policy, permission profile, path scope, network scope, tool DAG stage, human override | Shows whether a successful result came through an acceptable path |
| Review trace | reviewer decision, required follow-up, promoted lesson, incident closure | Closes the loop from one run into memory, eval, or policy improvement |

**Harness-condition sheet:** every workflow and benchmark stores the same minimum condition record: model/backend, server/skill versions, prompt/template versions, exposed tools, tools actually used, denied tools, permission mode, write/network scope, sandbox, context policy, verification gates, telemetry schema, redaction policy, retry limits, cost limits, recovery/checkpoint mode, and final outcome. Benchmark reports without this record are invalid for release decisions because the model result and harness configuration cannot be separated.

**Stage-aware harness model:** the server treats repository harness maturity as typed state, not prose. `S0` means greenfield, `S1` means walking skeleton, `S2` means growing repository with tests/CI, and `S3` means production release process. Each stage preserves the lower-stage controls: branch discipline, hard constraints, sandboxing, verification, manifest regression, readiness scoring, incident paths, and governed evolution. A higher stage may specialize policies for risk, language, or deployment, but it must not relax earlier hard constraints.

**Instruction discovery and drift:** the canonical hard constraints and project policy live in `AGENTS.md`. Copilot and Codex CLI read that file natively; Claude Code receives it through `CLAUDE.md` with an `@AGENTS.md` import. Runtime overlays such as `CLAUDE.md`, `.github/copilot-instructions.md`, and `.codex/INSTRUCTIONS.md`, selected `SKILL.md` files, and the session plan may narrow or specialize the policy, never widen it. `classify_harness_drift` marks artefacts as `missing`, `stale`, `relaxed`, `out-of-stage`, or `clean`; `relaxed` drift blocks automated refresh, release gates, and higher-autonomy workflows until reviewed because it indicates a weakened hard constraint.

**Permission and tool DAG:** workflows advance through explicit stages. A stage exposes only the tools needed for that stage, and policy is monotonic: delegation or retries may narrow permissions but never silently widen them.

| Stage | Allowed capability | Default blockers |
|---|---|---|
| `plan` | read resources, search, classify scope, compute readiness | writes, shell execution, network |
| `localize` | graph/query tools, SARIF reads, bounded source reads | edits, broad shell, package install |
| `repair` | scoped edit proposal, generated predicates/tests, diff snapshots | out-of-scope paths, generated files unless allowed |
| `verify` | allowlisted build/test/SAST/contract/maintainability checks | arbitrary commands, unpinned network downloads |
| `review` | read diff, evidence, run record, gates, incident status | writes and execution |
| `promote` | reviewed memory/rule/eval/policy update | unreviewed prose memory, direct policy mutation by LLM |

**Budget and context controls:** token, tool-call, wall-clock, retry, trace-size, and artefact-size budgets are tracked as run events. The server warns at soft thresholds, checkpoints before hard thresholds, and can force `unknown` or human review when compaction removes evidence needed for an audit-grade verdict. Large outputs are stored as artefacts with hashes; LLM context receives scoped snippets or summaries linked back to those artefacts.

**Live monitors:** the server emits monitor alerts and persists them in the run record for:
- repeated identical tool calls or identical failing gates with no code/evidence change
- context growth without new evidence
- permission-denial storms or attempted out-of-scope writes
- stale or mixed worktree snapshots in a verdict
- budget exhaustion, retry storms, or unexpected latency spikes
- secret/PII redaction failures in prompts, logs, traces, or generated reports
- "outcome-correct but process-noncompliant" runs, such as a passing patch produced without required gates
- cumulative risk across a session, where individually harmless operations combine into a policy violation

**Operational review loop:** `run_operational_review` replays a run record and returns: trace completeness, policy compliance, budget behaviour, anomaly list, evidence gaps, gate adequacy, reviewer decision, incident follow-ups, and promotion candidates. Promotion candidates are typed: memory record, detector, eval regression, SARIF/ruleset update, readiness task, or governance-policy change. The product explicitly rejects "remember this" prose as durable memory unless it is converted into a schema-grounded record with source links, owner, expiry, and rollback path.

**Incident model:** incidents are first-class evidence nodes. An incident records impact, timeline, root cause, containment, remediation, evidence links, detector/regression added, and closure reviewer. Common incidents include repeated-loop, out-of-scope write attempt, secret exposure, unsafe command request, verification bypass, stale-index verdict, unreviewed memory write, and budget hard-stop. Closed incidents feed F11 and the evaluation harness; they are not just support tickets.

---

## 3. Skill — `code-audit`

The skill is a client-side orchestration layer that uses the MCP server as its backend. It exposes three developer-facing workflows plus two operator-facing workflows as structured, repeatable operations, and maps those workflows onto task-capable workflow tools plus private templates such as `investigate`, `repair`, `audit`, and `operational-review`. Because the heavy lifting is pre-built in the index, each skill invocation starts from pre-fetched, pre-summarised, structured context. It reads bounded source spans only when the evidence model says the exact code is needed for a patch, predicate, or finding.

`code-audit` is the workflow family name, not a fourth user workflow. Developers choose from `implementation-check`, `bug-resolve`, and optional `patch-review`; operators/reviewers can also choose `operational-review` or `readiness-audit` when they need to inspect a run, diagnose failures, or improve the tool's controls.

The skill uses public MCP **Prompts** for user-selected workflows, private templates for decomposition, **Resources** for evidence, **Tools** for targeted queries and gates, **Tasks** for long runs, and optional **Sampling** for parallel review subagents.

### 3.1 User-facing workflows

| Workflow | User intent | Internal mapping |
|---|---|---|
| `implementation-check` | Given a design/spec/feature description, determine whether the current implementation satisfies it | Public prompt + `run_implementation_check`, using graph, repo-QA, static verdict, optional dynamic verdict, and calibrated aggregation |
| `bug-resolve` | Given a bug report, locate the likely root cause, propose a fix, verify it, and explain blast radius/downstream impact | Public prompt + `run_issue_resolution`, which chains `investigate` → `repair` → gates → `blast-radius` |
| `patch-review` | Given an existing diff, review correctness, safety, compatibility, and side effects | Public prompt + `run_patch_review`, using patch-risk, SAST/SARIF, contract, and behavioural drift gates |
| `operational-review` | Given a workflow run, reconstruct what happened, whether policy/gates were followed, and what should be improved | Public/operator prompt + `run_operational_review`, using run records, harness-condition sheets, monitor alerts, incidents, and promotion gates |
| `readiness-audit` | Given a repository, decide whether the tool can run higher-autonomy workflows safely and usefully | Public/operator prompt + `run_readiness_audit`, using harness stage, drift state, readiness score, build/test/SAST availability, docs/spec links, policy coverage, and maintainability oracles |

All five workflows start by creating a run record and harness-condition sheet. Developer workflows write operational events as they run; operator workflows read those events and may append reviewer decisions, incidents, or approved promotion records. A missing run record is a workflow failure, not a logging warning.

### 3.2 Internal `investigate` mode

**Entry point:** `investigate(issue_text="<bug report>")` (private skill template)

**Mode mark:** `investigate` is `[HYBRID]`. Retrieval, graph slicing, SARIF/test evidence loading, memory filtering, and trace calls are `[PY-CODE]`; per-candidate explanations and final ranking are `[LLM]` / `[ML-MODEL]` and must cite evidence.

**Workflow:**
1. `[PY-CODE]` `retrieve_memory(issue_text, phase="investigate")` — pulls coarse issue-class and FL-class hints, rejecting historically low-utility memories. Paper anchors: `agent-her`, `evo-memory`, `memory-management-empirical`, `c2f-grounded-memory`.
2. `[ML-MODEL]` + `[PY-CODE]` `get_relevant_files(issue_text)` — embedding/retriever search across all registered repos returns a ranked file list, then Python applies graph and policy constraints. Paper anchors: `fl-context-2026`, `rgfl`, `repo-aware-kg`.
3. `[PY-CODE]` `get_graph_slice(top_files, edge_types=["calls","imports","dataflow","tests","documents","warned_by"])` — loads the typed ego-network for the top candidates as a Resource. Paper anchors: `arise`, `locagent`, `repograph`, `codexgraph`, `rig`.
4. `[PY-CODE]` + optional `[LLM]` reads the pre-cached summary Resource and any linked SARIF/build/test evidence for each candidate symbol; if the next decision depends on exact logic, reads a bounded code span with provenance instead of wholesale file context. Paper anchors: `reporepair`, `rig`, `predicatefix`.
5. `[LLM]` ranks candidates with **per-candidate reasoning** (RGFL pattern): emits a structured explanation linking the issue symptom to each candidate's inferred behaviour before producing the ranking — not just similarity scores. Paper anchors: `rgfl`, `fl-context-2026`.
6. `[HYBRID]` If static analysis is inconclusive or risk is high and a reproduction is available or generated: `capture_trace(reproduction_script, scope=relevant_modules)` — async task, returns scope-filtered, LLM-compressed trace; raw trace dumps are retained as artefacts but never inserted into context. Paper anchors: `trace-prompt`, `daira`, `tracerepair`, `agent-coevo`.
7. `[PY-CODE]` If the top suspect is near a cross-language boundary: `trace_cross_language(suspect_symbol)` follows the chain automatically through all registered plugins (IDL → C++ → Python → HTTP → JS/TS); the full multi-hop sequence is returned as ordered nodes. Paper anchors: `rig`, `logiclens`, `eagle-x`, `swe-polybench`.

**Output:** ranked suspect locations with reasoning chains, graph/SARIF provenance, memory hints used or rejected, and optional compressed dynamic trace

---

### 3.3 Internal `repair` mode

**Entry point:** `repair(location="<file>:<line or symbol>")` (private skill template)

**Mode mark:** `repair` is `[HYBRID]`. Patch/spec/certificate generation is `[LLM]`; loading context, applying edits, SARIF/build/test execution, interface checks, and risk gating are `[PY-CODE]` / `[ML-MODEL]`.

**Workflow:**
1. `[PY-CODE]` Load graph slice + summaries + relevant memory hints for the fault location from Resources. Paper anchors: `arise`, `reporepair`, `agent-her`, `c2f-grounded-memory`.
2. `[PY-CODE]` Check whether the faulty symbol participates in any cross-language interface: if so, load the interface contract Resource — the patch must preserve the interface contract. Paper anchors: `rig`, `logiclens`, `mids-valve`, `jml-autodoc`.
3. `[HYBRID]` If the repair starts from a SARIF alert, call `run_sast_repair`; otherwise generate a patch in unified diff format using the graph slice and summaries. Paper anchors: `predicatefix`, `codecureagent`, `specrover`.
4. `[LLM]` Generate `preconditions(…)` / `postconditions(…)` spec for the changed function (SpecRover pattern) — shipped alongside the patch as an auditable artefact. Paper anchors: `specrover`, `codespecbench`, `jml-autodoc`.
5. `[LLM]` Verify the patch via **execution-free certificate reasoning** (agentic-code-reasoning pattern): the LLM produces DEFINITIONS → PREMISES → per-execution-path CLAIMS → COUNTEREXAMPLE search → CONCLUSION. This certificate is auditable soft evidence; it never replaces deterministic gates when a runnable environment exists. Paper anchors: `agentic-code-reasoning`.
6. `[PY-CODE]` Run deterministic gates when available: SAST/SARIF delta, build/test, interface-contract compatibility, and PoC⁺/regression tests for vulnerability-class repairs. Paper anchors: `predicatefix`, `pvbench`, `codecureagent`, `agent-coevo`.
7. `[ML-MODEL]` + `[PY-CODE]` Run `classify_patch_risk(diff)` and block or escalate if the result is `correct-but-overfit`, `vulnerable`, `vulnerability-introducing`, or low-confidence. Paper anchors: `compass`, `correct-not-safe`, `redteam-apr`, `logiceval`, `why-llms-fail-secpatch`.

**Output:** unified diff patch + pre/post-condition spec + execution-free verification certificate + SARIF/test delta + patch-risk verdict

---

### 3.4 Internal `audit` prompt mode

**Entry point:** `audit(mode=patch|implementation_check, content="<diff or design/spec text>")` (private skill template)

**Mode mark:** `audit` is `[HYBRID]`. Parallel review agents, clause interpretation, soft QA, and certificates are `[LLM]`; SARIF/test/contract gates, aggregation policy, calibration, and final blocking decisions are `[PY-CODE]` / `[ML-MODEL]`.

**If auditing a patch:**

The patch is checked by an adapted **4-agent parallel review**. The paper pattern (CodeX-Verify) uses Correctness, Security, Performance, and Style agents; this product replaces Style with Compatibility because cross-language/API/ABI breakage is a first-class SCA risk. The +39.7pp result belongs to the original paper setup and must be re-measured for this adapted role set:

| Agent | Focus | Paper anchors |
|---|---|---|
| Correctness | Logic errors, edge cases, exception handling paths | `multi-agent-info-theory`, `agentic-code-reasoning` |
| Security | CWE classes, OWASP vulnerabilities, secret leakage; `correct-not-safe` finding: passing tests ≠ safe | `correct-not-safe`, `redteam-apr`, `logiceval`, `why-llms-fail-secpatch` |
| Performance | Algorithmic complexity, memory leaks, resource usage | `multi-agent-info-theory` |
| Compatibility | API contract breaks, ABI compatibility, cross-language interface contract preservation | `rig`, `logiclens`, `swe-polybench`, `mids-valve` |

Each agent reads from pre-summarised Resources rather than raw file context. The agents are spawned via MCP **Sampling** (the server asks the client to invoke the LLM for each agent role). An aggregator combines the four verdicts with deterministic gates:

| Gate | Signal | Source | Paper anchors |
|---|---|---|---|
| `[PY-CODE]` SAST delta | disappeared / appeared SARIF alerts | `run_static_analysis` | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair` |
| `[ML-MODEL]` Patch-risk class | `safe`, `correct-but-overfit`, `vulnerable`, `vulnerability-introducing` | `classify_patch_risk` | `compass`, `pvbench`, `correct-not-safe`, `why-llms-fail-secpatch` |
| `[PY-CODE]` Contract compatibility | interface/API/ABI break flag | graph + interface plugin resources | `rig`, `logiclens`, `mids-valve`, `jml-autodoc` |
| `[PY-CODE]` / `[HYBRID]` Behavioural drift | spec/test delta, PoC⁺ pass-rate where relevant | build/test evidence + `pvbench`-style checks | `agent-coevo`, `codespecbench`, `pvbench` |

The output is a structured multi-axis report: functional ✓/✗ + security risk class + calibrated uncertainty + behavioural drift score + API/ABI break flag + merge/block recommendation.

**If running an implementation check:**

Use the full §13.1 seven-stage DAG, not only a soft document comparison. This workflow checks whether implementation satisfies a design/spec/feature clause; it is not a review of the spec's writing quality.

| Stage | Tooling | Output | Paper anchors |
|---|---|---|---|
| `[LLM]` 1. Intent parser | KGACG-style planner over Markdown/PDF/HTML | `{id, text, scope, priority}` intent clauses | `kgacg` |
| `[HYBRID]` 2. Structured intent | MIDS-valve ontology pattern | RDF/JSON-LD-like intent graph keyed by clause ID | `mids-valve` |
| `[HYBRID]` 3. Executable contract | JML-Autodoc / PredicateFix / Semgrep / CodeQL / tests | one predicate, contract, or assertion artefact per clause | `jml-autodoc`, `predicatefix`, `codespecbench` |
| `[HYBRID]` / `[ML-MODEL]` 4. Soft NL probe | `classify_repo_question` + `answer_repo_question` | Boolean answer + confidence + cited graph nodes | `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa`, `beyond-code-snippets` |
| `[PY-CODE]` 5. Repository graph slice | `get_graph_slice` / `trace_cross_language` | symbol-rooted graph with call, data-flow, test, document, and interface edges | `arise`, `repograph`, `codexgraph`, `rig`, `logiclens` |
| `[PY-CODE]` 6a. Static verdict | `run_static_analysis` over generated predicates | `{fired, locations[]}` as SARIF | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair` |
| `[PY-CODE]` / `[HYBRID]` 6b. Dynamic verdict | Agent-CoEvo-style regression or reproduction test when available | `{passed, failure_trace}` with compressed trace only | `agent-coevo`, `trace-prompt`, `daira`, `tracerepair` |
| `[PY-CODE]` / `[ML-MODEL]` 7. Verdict aggregator | Bayesian fusion / calibrated rule model | `{satisfied, violated, unknown, confidence}` per clause | `codespecbench`, `why-llms-fail-secpatch`, `swe-qa`, `coreqa` |

Aggregation rule: a hard predicate firing is authoritative failure with provenance; a hard predicate pass plus high-confidence repo-QA/dynamic evidence can pass; low-confidence behaviour-tracing questions remain **UNCERTAIN** and require human review. The stage-7 aggregator must meet ECE ≤0.10 on the Vul4J calibration set before implementation checks are allowed to auto-pass release gates.

> **Repo-QA accuracy ceiling (§13.6 Gap 6):** accuracy varies by question type. File-localisation QA reaches ~91% EM with a fine-tuned model (`repo-path-retrieval-llm`); cross-file behaviour-tracing QA remains 40–60% on `swe-qa`/`coreqa`. The seven-stage implementation check keeps the hard predicate/SARIF verdict as the authoritative signal and uses repo-QA confidence to decide when to trust the soft verdict vs. escalate to a human reviewer. For behaviour-tracing questions, do not rely on repo-QA alone for high-stakes implementation checks until KG-augmented repo-QA accuracy reaches ≥70% (the §13.6 ship-gate).

**Gap 1 status (§13.1 of the research report):** the design/spec → executable contract → implementation-equivalence loop is now **bridged** by three published bricks: `kgacg` (arXiv 2510.19868 — software requirements spec + architectural design doc → executable code via three-agent collaboration; the first end-to-end prototype that takes an external design document as input), `mids-valve` (arXiv 2510.01736 — machine-interpretable engineering design standards as W3C ontologies; the design-standard → ontology → instance-check pattern), and `jml-autodoc` (arXiv 2506.09230 — JML formal pre/post conditions as executable contracts for LLM-generated documentation). **Assembly is engineering, no longer research.** The one residual open question — calibrating the stage-7 verdict aggregator (Bayesian fusion over static predicate, soft repo-QA, and dynamic verdicts) to ECE ≤ 0.10 on Vul4J — is a measurable one-off calibration step, not a research blocker. Refer to §13.1 for the full 7-stage DAG glue-script design.

---

## 4. Feature and function design

This section defines the tool's feature set. Each feature is described as a product capability: user need, evidence consumed, methodology, output, confidence behaviour, and research anchors. It deliberately avoids implementation packaging, storage-table, CLI, or deployment details.

Feature IDs:

| ID | Feature | Primary user question |
|---|---|---|
| F1 | Repository intelligence graph | "What code facts can the tool know before the LLM starts reasoning?" |
| F2 | Fault localisation and relevant-context discovery | "Where is the likely root cause, and which files matter?" |
| F3 | Repository question answering and behaviour tracing | "Can the tool answer a repo-scoped behaviour or location question with evidence?" |
| F4 | Implementation-check | "Does the current implementation satisfy this design/spec/feature requirement?" |
| F5 | Bug-resolve | "Can the tool locate, explain, fix, and verify a reported bug?" |
| F6 | Patch-review and patch-risk classification | "Is this patch correct, safe, compatible, and low-risk?" |
| F7 | Static-analysis alert repair | "Can the tool repair a SARIF/SAST alert using the analyser's own predicates?" |
| F8 | Cross-language and cross-repository blast radius | "What breaks downstream across language and repo boundaries?" |
| F9 | Dynamic trace augmentation | "When static evidence is inconclusive, what runtime evidence should be used?" |
| F10 | Trajectory memory and experience replay | "Which prior investigations or repairs are useful, and which should be ignored?" |
| F11 | Operational harness, telemetry, and continuous improvement | "Can we reconstruct, review, and improve how the tool itself ran?" |

### 4.1 End-to-end data flow

```
Repositories (C/C++, Python, JS/TS, .idl files)
     │
     ├── tree-sitter       ──── typed AST nodes ─────────┐
     ├── universal-ctags   ──── symbol definitions ──────┤
     ├── libclang/clangd   ──── C/C++ calls/types ───────┤
     ├── pyan3             ──── Python call/import graph ─┤
     ├── ts-morph / madge  ──── JS/TS call/import graph ──┤
     ├── RIG/SPADE-style   ──── build/test evidence ──────┤
     ├── git log/blame     ──── commit history ───────────┤
     ├── embedding API     ──── semantic vectors ─────────┤─→ graph_build() → local index
     ├── Semgrep/CodeQL/   ──── SARIF v2.1.0 alerts ──────┤   (typed graph + SARIF +
     │   Bandit/SonarQube       predicates/rules          │    eval + memory stores;
     └── Interface plugins (one per interface type):      │    refreshed by graph_update())
           omniORB-IDL plugin ── IDL AST + C++ + Python link ─┤
           HTTP-REST plugin   ── routes + JS/TS clients ──────┤
           WebSocket plugin   ── events + listeners ──────────┤
           [future plugins]   ── gRPC, protobuf, etc. ────────┘
                                                         │
                    file watcher / git hook / user request
                                   → graph_update()       │
                    (MCP task, poll + optional status)   │
                                                         ↓
                              MCP Resources ──── graph, schema, summaries,
                              (subscribable)     blame, interfaces, SARIF,
                                                   build evidence, eval runs,
                                                   trajectory memory
                                                         │
                              MCP Tools ────────── cross-language query,
                              (model-controlled)   build, live trace, SAST,
                                                   patch risk, RDS, memory
                                                         │
                              MCP Prompts ─────── implementation-check,
                              (public)            bug-resolve, patch-review
                                                         │
                              Private templates ─ investigate, repair,
                                                   audit, blast-radius,
                                                   sast-repair, risk-classify,
                                                   evaluate
                                                         │
                              code-audit Skill ─── orchestrates LLM reasoning,
                                                   deterministic gates, and
                                                   calibrated workflow verdicts
                                                         │
                              Operational harness ─ run records, harness
                              plane                  conditions, policy gates,
                                                     budgets, monitors,
                                                     incidents, promotion hooks
```

### 4.2 Shared evidence and verdict model

All user-facing workflows return structured verdicts instead of free-form opinions. This is the common contract across `implementation-check`, `bug-resolve`, `patch-review`, `run_sast_repair`, and `blast-radius`.

| Field | Meaning | Why it matters |
|---|---|---|
| `verdict` | `satisfied`, `violated`, `safe`, `risky`, `unknown`, or workflow-specific equivalent | Prevents vague "looks good" answers |
| `confidence` | Calibrated numeric confidence or ordinal bucket | Enables ECE-based release gates |
| `evidence` | Files, symbols, graph nodes, SARIF alerts, tests, interface contracts, traces, memory records | Makes every claim auditable |
| `run_record` | Run ID, harness-condition ID, workflow stages, tool calls, approvals/denials, budget events, compaction events, gate results, and incidents | Makes the tool's process reviewable, not only its final claim |
| `reasoning_chain` | Short, per-candidate or per-clause rationale grounded in evidence | Copies RGFL-style explain-before-rank behaviour |
| `uncertainty` | Missing tools, stale index, low-confidence edges, ambiguous interface links, low repo-QA confidence | Stops soft LLM guesses from becoming hard conclusions |
| `recommended_action` | Accept, reject, inspect a location, run a test, add a predicate, or request human review | Makes the output operational |

Evidence strength is ordered as follows:

| Evidence class | Examples | Default role |
|---|---|---|
| Hard static evidence | Parser graph, type information, CodeQL/Semgrep/Bandit/SonarQube SARIF, generated predicates that fire | Can directly fail a verdict when provenance is clear |
| Hard dynamic evidence | Reproduction tests, regression tests, PoC⁺ tests, scoped traces | Can pass or fail behaviour claims when environment is trusted |
| Structured repository evidence | Typed graph slices, interface contracts, build/test evidence, blame history | Narrows scope and explains impact |
| Calibrated model evidence | Patch-risk classifier, repo-QA confidence, stage-7 implementation-check aggregator | Supports a verdict only within measured calibration bounds |
| Soft LLM evidence | Summaries, candidate explanations, contract drafts, repair certificates | Treated as hypotheses until checked by stronger evidence |

The design copies three cross-cutting lessons from the research report:
- `fl-context-2026`: localisation quality dominates repair quality, so every workflow must expose which files/symbols it used.
- `correct-not-safe` / `pvbench`: functional success is not safety; patch verdicts must include vulnerability and overfitting signals.
- `codespecbench` / `swe-qa` / `coreqa`: repository-level intent understanding is still unreliable, so implementation checks must preserve `unknown` as a first-class verdict.

Verdict precedence is intentionally conservative:
- Hard failures from static analysis, contract compatibility, required tests, or PoC⁺ checks can force `violated`, `risky`, or `block`.
- Hard failures from governance gates — out-of-scope write attempt, missing approval, missing required verification, stale/mixed snapshot, secret redaction failure, or budget hard-stop — can force `unknown`, `block`, or incident review even when the code-level answer looks plausible.
- Calibrated model evidence can raise or lower confidence only within its measured calibration bounds.
- Soft LLM certificates and summaries can explain a verdict but cannot alone auto-pass implementation-check or patch-review gates.
- Mixed-snapshot evidence, stale indexes, missing tool support, or uncalibrated classifier families force `unknown` / human review.

### 4.3 F1 — Repository intelligence graph

**User need:** before an LLM reasons about a repository, the tool should know stable code facts: symbols, calls, imports, data flow, tests, documents, SAST alerts, build evidence, git history, and cross-language interfaces.

| Aspect | Design |
|---|---|
| Implementation mode | `[PY-CODE]` core graph/index/persistence; `[HYBRID]` only for cached summaries and document/spec binding |
| Inputs | Source files, build metadata, tests, docs/specs, SARIF runs, git history, interface definitions |
| Core method | Build a typed repository graph with nodes for files/symbols/interfaces/evidence and edges for `contains`, `imports`, `calls`, `dataflow`, `tests`, `documents`, `implements`, `warned_by`, and `fixed_by` |
| LLM role | Generate cached symbol summaries and help bind documents/spec clauses to graph nodes; never silently create hard graph facts |
| Outputs | Graph resources, graph slices, symbol summaries, build/test evidence, SARIF-linked nodes, cross-language interface records |
| Confidence behaviour | Parser/analyser/build edges are high confidence; heuristic and LLM-derived edges carry lower confidence and must be surfaced as such |
| Paper anchors | `arise`, `locagent`, `cosil`, `repograph`, `codexgraph`, `repo-aware-kg`, `rig`, `logiclens` |

Research methodology used:
- ARISE/LocAgent/CoSIL/RepoGraph/CodexGraph converge on graph navigation as the core substrate for repo-scale localisation.
- RIG and LogicLens justify making build/test evidence and cross-language links part of the same graph rather than side-channel metadata.
- RepoRepair and SpecRover justify hierarchical natural-language summaries, but only as compressed context; they do not replace graph evidence.

Function requirements:
- The graph must support ego-network retrieval around files, symbols, tests, SARIF alerts, and interface contracts.
- Graph slices must include provenance and confidence, because downstream workflows need to distinguish parser facts from inferred links.
- Document/spec nodes must be linked to code nodes through `documents` edges so implementation-check can trace each clause to candidate implementation locations.
- SARIF alerts must be linked through `warned_by` edges so static-analysis findings can trigger repair and patch-risk workflows.
- Generated contract artefacts, tests, runtime traces, patches, and verdicts must be graph nodes, not loose files, so every user-facing finding can be traced back to a code snapshot and evidence chain.
- Every graph slice returned to an LLM must carry `git_sha` or `worktree_snapshot_id`; stale or mixed-snapshot evidence forces `unknown` rather than a confident verdict.

### 4.4 F2 — Fault localisation and relevant-context discovery

**User need:** given an issue report or failing symptom, rank the most likely fault locations and the smallest useful context set.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: deterministic retrieval/graph/SBFL features plus `[LLM]` candidate explanations and ranking; optional `[ML-MODEL]` retrievers |
| Inputs | Issue text, failing test output if present, changed files, blame history, SARIF warnings, graph slices, optional memory hints |
| Core method | File-level retrieval first, graph-neighbour expansion second, per-candidate reasoning third, line/symbol narrowing last |
| Outputs | Ranked files/symbols with reasoning, supporting graph paths, relevant tests, SARIF warnings, and rejected alternatives |
| Confidence behaviour | High confidence requires agreement between semantic retrieval and graph/static evidence; low agreement produces an `uncertain` localisation |
| Paper anchors | `fl-context-2026`, `rgfl`, `arise`, `locagent`, `cosil`, `hafixagent`, `repo-aware-kg` |

Research methodology used:
- `fl-context-2026` reports that file-level fault localisation alone gives 15-17x repair improvement over no-file context. Therefore the feature optimises for high-quality file ranking before fine line ranking.
- The same study warns that excessive line-level expansion can add noise. Therefore the design keeps line windows tight and prefers file/symbol ranking plus graph evidence.
- RGFL motivates per-candidate explanations before final ranking, not just vector similarity scores.
- HAFixAgent motivates using blame/history as a cheap prior, especially when the issue mentions regressions or recently changed behaviour.
- AutoCodeRover/FlexFL-style hybrid localisation motivates adding SBFL/Ochiai or coverage priors when a failing test exists, but treating those priors as optional because many issue reports have no runnable failure.

Functional flow:

1. Normalize the issue into symptoms, expected behaviour, observed behaviour, mentioned APIs/files, and error strings.
2. Retrieve candidate files using semantic search, issue keywords, SARIF alert proximity, doc/spec links, and optional memory.
3. If failing tests and coverage are available, compute a suspiciousness prior (for example Ochiai/SBFL) and merge it as a feature, not as an override.
4. Expand candidates through bounded graph neighbours: callers, callees, imports, tests, documents, data-flow, and interface edges.
5. Apply the 6-10 relevant-file sweet spot from `fl-context-2026` as a default starting budget, then tune by language, repository size, RDS feature vector, and measured FL accuracy. Exceeding that budget requires an explicit uncertainty note.
6. For each candidate, produce a short evidence-grounded explanation: why this location could cause the symptom, what evidence supports it, and what evidence weakens it.
7. Return top-N candidates with confidence, graph paths, and recommended next checks.

### 4.5 F3 — Repository question answering and behaviour tracing

**User need:** answer repo-scoped questions such as "where is this behaviour implemented?", "what happens after this request?", or "which files enforce this rule?" with cited evidence.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[PY-CODE]` question routing and graph traversal; `[LLM]` answer synthesis; optional `[ML-MODEL]` path retrieval |
| Inputs | Natural-language question, optional repo/language scope, graph resources, summaries, interface contracts |
| Core method | Classify the question, route file-location questions through path retrieval, and route behaviour-tracing questions through NL-to-graph querying plus typed graph traversal |
| Outputs | Answer, cited files/symbols/graph paths, confidence, and `unknown` when evidence is insufficient |
| Confidence behaviour | File-location QA can be trusted at higher confidence than cross-file behaviour tracing; behaviour answers require graph provenance |
| Paper anchors | `repo-path-retrieval-llm`, `swd-bench`, `swe-qa`, `coreqa`, `beyond-code-snippets`, `repochat`, `repograph`, `codexgraph` |

Question classes:

| Class | Examples | Method |
|---|---|---|
| `file-loc` | "Where is login validation implemented?" | AST-derived file-path retrieval plus graph confirmation |
| `symbol-loc` | "Which function parses this IDL method?" | Symbol lookup plus interface graph links |
| `behaviour-trace` | "What happens when the frontend calls this endpoint?" | NL-to-graph traversal across calls, routes, events, and data-flow |
| `contract-check` | "Where is this spec clause enforced?" | Document/spec node binding plus predicate/static evidence |
| `other` | Ambiguous or unsupported questions | Ask for scope or return `unknown` |

Research methodology used:
- `repo-path-retrieval-llm` shows file-path retrieval can reach much higher accuracy when trained on AST-derived QA pairs.
- `swe-qa` and `coreqa` show behaviour-tracing QA remains substantially harder, often in the 40-60% range.
- `repochat` motivates translating natural-language behaviour questions into graph queries instead of relying on vanilla RAG answers.
- Therefore the feature must not collapse all repo-QA into one confidence regime. File-location and behaviour-tracing answers have separate thresholds.

Acceptance behaviour:
- File-location answers can support automated workflows only after the local `swd-bench` Functionality-Localization gate reaches the configured threshold.
- Behaviour-tracing answers remain supporting evidence until the graph-augmented `swe-qa` / `coreqa` behaviour subset reaches the ≥70% ship-gate from the research report.
- Any answer that cites only summaries or LLM reasoning, with no graph path or code/SARIF/test evidence, returns `unknown` for audit-grade workflows.

### 4.6 F4 — Implementation-check

**User need:** given a design document, feature request, requirement, or spec, determine whether the current implementation satisfies each clause.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[LLM]` clause extraction / draft contracts / soft QA; `[PY-CODE]` graph grounding, predicate execution, evidence storage, and verdict policy; `[ML-MODEL]` calibration where used |
| Inputs | Design/spec text, linked docs, target repo scope, graph resources, SARIF/static analysis, optional tests/traces |
| Core method | Seven-stage design/spec → intent → contract → graph → static/dynamic verdict → calibrated aggregation DAG |
| Outputs | Clause-by-clause verdict matrix with `satisfied`, `violated`, or `unknown`; evidence citations; confidence; missing evidence |
| Confidence behaviour | Hard predicate failures dominate; soft repo-QA cannot auto-pass high-stakes behaviour clauses without supporting graph/static/dynamic evidence |
| Paper anchors | `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `codespecbench`, `swe-qa`, `coreqa`, `agent-coevo` |

Clause types:

| Clause type | Example | Preferred evidence |
|---|---|---|
| Functional behaviour | "The API retries transient failures three times." | Graph path + tests or generated predicate |
| Input validation | "Reject negative quantities." | Static predicate, validation code path, tests |
| Security requirement | "User data must not be logged." | SAST rule, data-flow, negative tests |
| Interface contract | "IDL method returns nullable status." | Interface contract + caller/callee graph |
| Cross-service behaviour | "Frontend update propagates to C++ service." | Cross-language trace through plugins |
| Non-functional expectation | "Must not add O(n²) path." | Static complexity/performance review plus tests where available |
| Documentation-only claim | "The UI should mention..." | Document-to-code/resource binding; often lower confidence |

Clause extraction contract:

| Field | Meaning |
|---|---|
| `clause_id` | Stable ID used through contract generation, graph grounding, verdicts, and reports |
| `text` | Atomic requirement text copied or minimally normalised from the source document |
| `scope` | repo, package, file, symbol, interface, route/event, or unknown |
| `priority` | must, should, may, or informational |
| `checkability` | hard-static, hard-dynamic, mixed, soft-only, or non-checkable |
| `target_candidates` | graph nodes, docs, interfaces, or unresolved names the clause may bind to |
| `risk_class` | functional, security, privacy, compatibility, performance, usability, or documentation |

The parser must preserve source spans and rejected interpretations. A clause that cannot be made atomic is split; a clause that cannot be grounded is not dropped, it becomes `unknown` with a missing-grounding reason.

Seven-stage method:

| Stage | Purpose | Research idea copied |
|---|---|---|
| 1. Intent extraction | Break the design/spec into atomic clauses with scope and priority | `kgacg` planner-agent style |
| 2. Structured intent | Convert clauses into a machine-checkable intent graph | `mids-valve` ontology pattern |
| 3. Executable contract | Generate predicate, assertion, test, JML-like pre/postcondition, or Semgrep/CodeQL rule where possible | `jml-autodoc`, `predicatefix`, `codespecbench` |
| 4. Soft repo probe | Ask targeted repo-QA questions for clause-to-code binding | `repo-path-retrieval-llm`, `swe-qa`, `coreqa` |
| 5. Graph grounding | Retrieve graph slices for candidate implementation locations and interface boundaries | `arise`, `repograph`, `codexgraph`, `rig` |
| 6. Static/dynamic verdict | Run predicates/SARIF checks and optional generated regression tests or traces | `predicatefix`, `agent-coevo`, `trace-prompt`, `daira` |
| 7. Aggregation | Fuse hard evidence, soft answers, dynamic evidence, and uncertainty into a calibrated verdict | `codespecbench`, `why-llms-fail-secpatch` |

Verdict rules:
- `violated`: hard predicate fires, required code path is absent, interface contract is broken, or dynamic evidence contradicts the clause.
- `satisfied`: hard predicate passes and graph/test/static evidence supports the clause with calibrated confidence.
- `unknown`: evidence is missing, repo-QA is behaviour-tracing only, graph links are ambiguous, or dynamic evidence is unavailable for a runtime-only claim.

Contract generation rules:
- Prefer existing project contracts, schemas, OpenAPI/proto/IDL files, tests, and analyser rules before generating new predicates.
- Generated predicates/tests must compile or lint before they can contribute hard evidence; otherwise they remain soft candidate artefacts.
- Security/privacy clauses default to SAST/data-flow predicates plus negative tests where possible; repo-QA alone cannot satisfy them.
- Interface clauses require both sides of the boundary: producer implementation and at least one consumer or generated stub.
- Dynamic-only clauses must state the required reproduction, environment, and flakiness policy before they can be auto-passed.

### 4.7 F5 — Bug-resolve

**User need:** given a bug report, locate the root cause, propose a fix, verify it, explain risk, and show blast radius.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[LLM]` repair/spec/certificate generation; `[PY-CODE]` localisation data, test/SARIF/build/interface gates, patch application, and trajectory capture; `[ML-MODEL]` risk scoring |
| Inputs | Bug report, optional failing tests/logs, current graph, SARIF alerts, blame history, build/test evidence, memory hints |
| Core method | Agentless-style control loop: investigate → repair candidates → deterministic gates → risk review → trajectory recording |
| Outputs | Root-cause explanation, ranked suspect list, proposed patch, pre/postcondition spec, verification certificate, gate results, blast-radius map |
| Confidence behaviour | Patch proposal is not a resolved verdict until localisation, repair rationale, deterministic gates, and patch-risk review agree |
| Paper anchors | `agentless`, `fl-context-2026`, `specrover`, `agentic-code-reasoning`, `agent-coevo`, `issue2test`, `assertflip`, `trace-prompt`, `daira` |

Research methodology used:
- `agentless` motivates a fixed, inspectable pipeline as the baseline: localisation, repair, validation. The feature should remain debuggable even when agentic loops are added.
- `SpecRover` motivates shipping a behavioural summary or pre/postcondition beside the patch so reviewers can audit intent.
- `agentic-code-reasoning` motivates execution-free certificates: definitions, premises, path claims, and conclusion.
- `agent-coevo` motivates generated behavioural constraints and regression checks when direct tests are weak.
- `issue2test` and `assertflip` motivate generating or transforming issue-anchored reproduction tests, while still treating generated tests as fallible artefacts that need execution and failure-reason filtering.

Functional flow:

1. Run F2 localisation and record top candidates plus rejected candidates.
2. If no failing test exists, attempt an issue-anchored reproduction test or pass-then-invert test; keep it separate from the production patch until it fails on the buggy version for the right reason.
3. Generate a repair hypothesis for each high-ranked candidate, including why the patch should affect the symptom.
4. Create or update pre/postconditions for changed functions and interface contracts.
5. Produce an execution-free verification certificate over important paths.
6. Run deterministic gates where available: tests, generated reproduction tests, SARIF delta, interface compatibility, and PoC⁺ checks for vulnerability-class bugs.
7. Run F6 patch-risk review before presenting a merge recommendation.
8. Run F8 blast-radius analysis over changed symbols and interfaces.

Patch selection rule: if multiple plausible patches pass visible tests, prefer the one with stronger localisation agreement, fewer changed graph nodes, lower patch-risk probability, no new SARIF alerts, and better generated-test/PoC⁺ survival. Do not select only by pass/fail count.

### 4.8 F6 — Patch-review and patch-risk classification

**User need:** review an existing diff for correctness, safety, compatibility, side effects, and overfitting.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[LLM]` review-agent analysis; `[PY-CODE]` diff/SARIF/test/interface checks and merge policy; `[ML-MODEL]` patch-risk classifier |
| Inputs | Diff, issue/spec context if available, graph slices for changed symbols, SARIF before/after, tests, interface contracts |
| Core method | Multi-axis review: correctness, security, performance, compatibility, behavioural drift, and calibrated patch-risk class |
| Outputs | Merge/block recommendation, risk class, per-axis findings, evidence, required follow-up checks |
| Confidence behaviour | Passing tests are insufficient; safety and overfitting risks must be separately scored |
| Paper anchors | `multi-agent-info-theory`, `correct-not-safe`, `redteam-apr`, `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch`, `rig` |

Review axes:

| Axis | Checks |
|---|---|
| Functional correctness | Does the diff address the intended symptom without breaking edge cases? |
| Security | Does it introduce or fail to remove CWE/OWASP-class vulnerabilities? |
| Patch overfitting | Does it satisfy visible tests while missing the root cause or PoC⁺ behaviour? |
| Behavioural drift | Does it change externally visible behaviour beyond the intended fix? |
| API/ABI/interface compatibility | Does it break callers, generated stubs, IDL/proto contracts, REST routes, or WebSocket events? |
| Performance/resource use | Does it introduce avoidable complexity, leaks, or expensive calls on hot paths? |

Patch-risk classes:

| Class | Meaning | Action |
|---|---|---|
| `safe` | Evidence supports functional correctness and no meaningful safety/compatibility regression | Can recommend merge if gates pass |
| `correct-but-overfit` | Patch likely passes visible tests but does not address root cause or PoC⁺ behaviour | Block or require stronger tests |
| `vulnerable` | Patch fails to remove the target vulnerability | Block |
| `vulnerability-introducing` | Patch introduces a new vulnerability or weakens a guard | Block |
| `unknown` | Evidence is insufficient or classifier is uncalibrated for this patch class | Human review required |

Classifier feature contract:

| Feature stream | Required data |
|---|---|
| AST diff | Changed node kinds, edit operation, touched symbols, edit distance, generated/stub file flag |
| SARIF delta | Rules disappeared, rules appeared, severity changes, taint/nullness/security class |
| Graph context | 2-hop callers/callees, cross-file data-flow, interface boundaries, tests exercising changed nodes |
| Test residue | Regression pass/fail, generated reproduction result, PoC/PoC⁺ result, flaky rerun entropy |
| Vulnerability prior | CWE or rule-family prior from Vul4J/SRS-style calibration where available |

Decision policy:
- A deterministic hard failure (new critical SARIF alert, broken interface contract, failing required test, failed PoC⁺ for a vulnerability fix) overrides a `safe` classifier label.
- A `safe` label is merge-supporting only when the classifier is calibrated for the patch's language and CWE/rule family.
- `correct-but-overfit` is emitted when visible tests pass but reproduction/PoC⁺, graph root-cause evidence, or semantic certificate disagree.
- Classifier explanations must cite the feature streams that drove the label; a bare LLM label is not a patch-risk verdict.

Research methodology used:
- `multi-agent-info-theory` motivates specialised parallel review roles rather than a single undifferentiated reviewer.
- `correct-not-safe`, `redteam-apr`, and `pvbench` motivate separating correctness from safety.
- `compass`, `logiceval`, and `why-llms-fail-secpatch` motivate a calibrated classifier with explicit feature evidence rather than an ungrounded LLM label.

### 4.9 F7 — Static-analysis alert repair

**User need:** given a SAST/SARIF alert, explain why it fires, retrieve fix knowledge, propose a patch, and verify that the alert disappears without new regressions.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[PY-CODE]` SARIF binding, predicate-example retrieval, analyser reruns, and tests; `[LLM]` alert explanation and patch/rule synthesis |
| Inputs | SARIF alert, rule ID, predicate ID if available, graph slice, examples from clean corpus, tests/build evidence |
| Core method | Alert → predicate explanation → graph slice → fix-knowledge retrieval → patch → SAST/build/test re-check |
| Outputs | Alert explanation, affected graph nodes, patch, SARIF delta, regression evidence, remaining warnings |
| Confidence behaviour | The alert is not considered fixed unless the original predicate no longer fires and no higher-severity new alert is introduced |
| Paper anchors | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair`, `codeql-rule-multiagent`, `agent-coevo` |

Research methodology used:
- `predicatefix` retrieves examples by negating the firing predicate and finding clean-code examples where the safe predicate pattern appears. This is fix-knowledge retrieval from the analyser's own logic, not generic semantic RAG.
- `codecureagent` motivates warning-driven repair with build, warning disappearance, and tests as the basic loop.
- `nullrepair` motivates domain-specific static-analysis workflows where safe/unsafe regions guide the prompt.
- `codeql-rule-multiagent` is reserved for evolving analyser rules, not for normal alert repair.

Functional flow:

1. Bind the SARIF location to graph nodes and surrounding code paths.
2. Explain the rule and predicate in developer-facing language.
3. Classify the alert as likely true positive, likely false positive, or unknown using rule metadata, path feasibility, data-flow reachability, suppressions, and historical project evidence.
4. Retrieve predicate-derived safe examples where possible.
5. Generate a code patch, suppression proposal, or rule-refinement proposal depending on alert classification; normal alert repair should prefer code patches, while confirmed false positives feed rule evolution.
6. Re-run the analyser and compare SARIF deltas.
7. Run tests or generated regression checks when available.
8. Emit remaining-risk notes when the alert disappears but the root-cause behaviour is not fully verified.

Rule-evolution boundary: `codeql-rule-multiagent` is not invoked during ordinary developer repair. It is an offline ruleset-quality workflow that may promote a refined query only after the §13.7 false-positive-reduction gate passes with zero true-positive loss.

### 4.10 F8 — Cross-language and cross-repository blast radius

**User need:** determine what a change can affect across files, languages, generated stubs, service boundaries, and repositories.

| Aspect | Design |
|---|---|
| Implementation mode | `[PY-CODE]` graph/interface traversal and impact grouping; `[LLM]` only for optional human-readable explanation of the impact map |
| Inputs | Changed files/symbols, graph slices, interface contracts, callers/callees, tests, downstream repos |
| Core method | Traverse typed graph edges outward from changed nodes, crossing interface-plugin boundaries by default |
| Outputs | Impact map grouped by direct callers, downstream behaviours, tests, interfaces, services, and repos |
| Confidence behaviour | Ambiguous interface links remain candidates with confidence; they are not treated as confirmed impact |
| Paper anchors | `rig`, `logiclens`, `eagle-x`, `swe-polybench`, `defects4c`, `arise` |

Blast-radius categories:

| Category | Examples |
|---|---|
| Local code impact | Callers/callees, imports, data-flow consumers |
| Test impact | Tests likely to exercise changed paths |
| Interface impact | IDL methods, generated stubs, HTTP routes, WebSocket events |
| Cross-repo impact | Client repos consuming changed contracts |
| Static-analysis impact | SARIF alerts newly reachable from changed nodes |
| Documentation/spec impact | Clauses or docs linked to changed symbols |

Research methodology used:
- RIG/LogicLens motivate cross-language repository graphs as first-class reasoning substrates.
- SWE-PolyBench/Defects4C motivate evaluating cross-language and C/C++ drift rather than assuming Python-only behaviour generalises.

Traversal requirements:
- Traverse confirmed interface edges by default; include ambiguous interface candidates in a separate "possible impact" bucket with confidence and reason.
- Bound traversal by change type: API/schema/IDL changes expand through consumers; internal implementation changes expand through callers/tests/data-flow; security-sensitive changes include SAST reachability and taint paths.
- For generated stubs, report both the source contract that should be changed and generated files that should not be manually edited.
- For C/C++, include ABI-relevant signatures, template instantiations, ownership/nullness edges, and build-target reachability when available.

### 4.11 F9 — Dynamic trace augmentation

**User need:** when static evidence is insufficient, collect runtime evidence without flooding the LLM with raw traces.

| Aspect | Design |
|---|---|
| Implementation mode | `[HYBRID]`: `[PY-CODE]` trace capture, isolation, filtering, and artefact storage; `[LLM]` trace summarisation/compression |
| Inputs | Reproduction script/test, static suspect list, scope filter, graph slice |
| Core method | Scope-filtered trace capture, state-diff summarisation, and LLM-compressed trace snippets |
| Outputs | Compressed trace, relevant path events, variable/state deltas, divergence points, uncertainty notes |
| Confidence behaviour | Dynamic evidence strengthens or weakens static hypotheses; raw trace volume alone is not evidence quality |
| Paper anchors | `trace-prompt`, `daira`, `tracerepair`, `agent-coevo` |

Research methodology used:
- `trace-prompt` shows naive trace dumps are unreliable and sometimes harmful.
- DAIRA and TraceRepair motivate structured dynamic signals: scoped traces, agent-guided debugging, state diffs, and debate/review over runtime observations.
- Therefore the feature is a fallback for ambiguity, not the default context source.

Trace capture contract:
- A trace run requires a reproduction command, timeout, environment snapshot, scope filter, and redaction policy.
- Raw traces are stored as artefacts; LLM context receives only compressed events, state diffs, branch decisions, and divergence points linked back to raw trace IDs.
- Language adapters are explicit: Python can use `sys.settrace`/Hunter-style tracing; JS/TS can use inspector/V8 hooks; C/C++ should prefer sanitizer, `rr`, `gdb`, or project-specific probes when a reproducible crash exists.
- A trace that cannot reproduce the issue weakens, but does not falsify, the static hypothesis unless the reproduction itself is trusted.

Dynamic evidence should be used when:
- F2 returns multiple plausible root causes with similar confidence.
- The issue is inherently runtime-dependent: concurrency, environment, stateful protocols, flaky tests, timing, or data-dependent behaviour.
- F4 implementation-check involves a clause that cannot be statically reduced to a predicate or graph path.
- F6 patch-review needs behavioural drift evidence beyond tests.

### 4.12 F10 — Trajectory memory and experience replay

**User need:** reuse prior successful and failed investigations without copying irrelevant or harmful past behaviour.

| Aspect | Design |
|---|---|
| Implementation mode | `[PY-CODE]` storage, retrieval filters, retention, and audit trail; optional `[ML-MODEL]` similarity/utility scoring; optional `[LLM]` hindsight relabelling |
| Inputs | Prior issues, localisation decisions, graph slices, patches, SARIF deltas, tests, outcomes, utility scores |
| Core method | Coarse-to-fine retrieval with hindsight relabelling, utility-aware eviction, and misalignment guard |
| Outputs | Memory hints for investigation, repair, alert repair, and patch review; rejected-memory notes when relevant |
| Confidence behaviour | High-similarity but historically low-utility memories are rejected; memory never overrides current hard evidence |
| Paper anchors | `agent-her`, `evo-memory`, `memory-management-empirical`, `graph-memory-rl`, `c2f-grounded-memory` |

Research methodology used:
- Agent-HER motivates reusing failed trajectories after relabelling the goal they actually teach.
- Evo-Memory motivates promote/demote/expire decisions instead of unbounded accumulation.
- Memory-management empirical work motivates guarding against error propagation from similar but low-utility records.
- Coarse-to-fine grounded memory motivates issue-class retrieval during investigation and concrete edit/predicate/test retrieval during repair.

Memory retrieval phases:

| Phase | Retrieved memory type | Use |
|---|---|---|
| Investigation | Similar issue classes, FL decisions, graph paths | Bias candidate ranking, with low confidence |
| Repair | Similar patch classes, predicates, tests | Suggest repair patterns or edge cases |
| Patch review | Similar risky diffs and safety failures | Surface overfitting or vulnerability patterns |
| Evaluation | Historical run outcomes and RDS features | Diagnose feature regressions |

### 4.13 F11 — Operational harness, telemetry, and continuous improvement

**User need:** make the tool/application run better over time by logging enough structured evidence to review runs, diagnose failures, constrain risky actions, measure operational quality, and promote reviewed lessons into memory, evals, rules, or policy.

| Aspect | Design |
|---|---|
| Implementation mode | `[PY-CODE]` for event capture, schema validation, permission decisions, budgets, monitor alerts, incident records, readiness scoring, and promotion gates; `[LLM]` only for optional reviewer summaries |
| Inputs | Workflow run events, harness-condition sheets, tool calls/results, graph snapshot IDs, diff snapshots, approvals/denials, budget/compaction events, verification results, monitor alerts, incidents, reviewer decisions |
| Core method | AgentTrace/AER-style append-only run ledger + OpenDev-style staged permissions/context budgets + Runtime-Governance-style deny-first policy + Workstream/Needle/TDAD-style readiness, maintainability, and behaviour-artifact tests |
| Outputs | Run record, process-compliance verdict, trace-completeness score, anomaly list, incident report, harness stage, drift findings, readiness score, maintainability-oracle results, prompt/manifest regression results, promotion candidates |
| Confidence behaviour | Missing or incomplete operational trace reduces confidence; required process violations can block or force human review even if code-level evidence passes |
| Paper anchors | `agenttrace`, `aer`, `opendev`, `runtime-governance`, `cqa`, `workstream`, `needle-repo`, `tdad`, `schema-grounded-memory`, `agentic-harness-engineering` |

Operational run record:

| Record field | Meaning |
|---|---|
| `run_id` / `workflow` | Stable ID and workflow type: implementation-check, bug-resolve, patch-review, operational-review, readiness-audit, or eval |
| `harness_condition_id` | Model/backend, versions, tool set, permissions, sandbox, context policy, verification gates, telemetry and redaction policy |
| `stage_events[]` | Stage transitions through plan/localize/repair/verify/review/promote, with timestamps and actor |
| `tool_events[]` | Tool call, arguments hash, scope, result status, output artefact hash, tokens, wall time, retry count, policy action |
| `context_events[]` | Resources loaded, graph snapshot IDs, code spans, summaries, compaction/checkpoint events, redaction events |
| `gate_events[]` | Build/test/SAST/contract/maintainability/prompt-regression results and why a gate passed, failed, or was skipped |
| `monitor_events[]` | Loop, drift, budget, stale-evidence, scope, secret, or cumulative-risk alerts |
| `review_events[]` | Human decision, incident closure, memory/eval/policy promotion decision |

Operational review verdicts:

| Verdict | Meaning | Action |
|---|---|---|
| `process-compliant` | Required stages, permissions, gates, and records are complete | Run can support release/eval evidence |
| `process-noncompliant` | Required approval, gate, redaction, or scope rule was violated | Block merge/release and open or update an incident |
| `trace-incomplete` | Run may be correct, but reconstruction is impossible | Human review required; do not promote to memory/eval |
| `budget-exhausted` | Context, token, tool, retry, or wall-clock hard limit was reached | Stop or checkpoint; final code verdict cannot auto-pass |
| `needs-readiness-work` | Repo/tool setup lacks required gates or evidence sources | Run readiness tasks before higher-autonomy workflows |

Development-harness contract:

| Contract element | Design requirement |
|---|---|
| Hard constraints | Default HC set covers no plaintext secrets, no writes outside the repository/path allowlist, explicit approval for destructive commands, no agent-executed irreversible migrations, deny-by-default network egress, and no red-class data in prompts/tool arguments/logs |
| Instruction precedence | `AGENTS.md` contains the mandatory HC constraints and project policy; `CLAUDE.md` imports it for Claude Code; runtime overlays and skills may specialize but never relax it; session plans inherit the effective policy |
| Stage monotonicity | `S0`-`S3` upgrades add controls only; skipped stages, readiness-axis regressions, and relaxed overlays block promotion |
| Local-agent workflow | Plan/read/localize/edit/verify/review/promote stages are recorded with tool DAG, path scope, budget, and gate evidence |
| Verify-before-commit | Agent-authored changes require deterministic checks plus trace/scope audit before commit or release evidence is accepted |
| Memory and lessons | Session notes remain artefacts until reviewed into schema-grounded memory, tests, detectors, rules, or policy with owner, expiry, source links, and rollback |

Continuous-improvement loop:

1. Capture every workflow as an append-only run record before judging output quality.
2. Run monitors during execution and again during operational review.
3. Convert repeated failures into typed incidents with containment, root cause, remediation, and evidence links.
4. Promote only reviewed lessons into one of five durable targets: schema-grounded memory, regression eval, monitor/detector, static-analysis rule, or governance policy.
5. Re-run the affected T1/T2 eval slice and the prompt/manifest regression suite before making a promoted lesson default behaviour.
6. Track whether the change improved success, reviewability, safety, latency/cost, and incident rate at fixed model/backend.

Anti-abuse and privacy rules:
- Raw prompts, full traces, and command outputs are not durable memory by default. They are artefacts with retention, redaction, and access policy.
- Secrets and red-class data are never inserted into model prompts, summaries, memory, or public reports; redaction failure opens an incident.
- The LLM cannot approve its own policy violation, promote memory, or waive required gates. It can propose a lesson; deterministic tools and reviewers decide.
- A run that passes tests through an unauthorized command path is recorded as an operational failure, not as clean success.

### 4.14 Feature interaction matrix

| Feature | Consumes | Produces | Feeds |
|---|---|---|---|
| F1 Repository graph `[PY-CODE]` / `[HYBRID]` | Code, docs, SARIF, build/test, interfaces | Typed graph, summaries, evidence resources | All other features |
| F2 Fault localisation `[HYBRID]` | Issue text, graph, SARIF, blame, memory | Ranked suspect locations | F5, F9, F10 |
| F3 Repo-QA `[HYBRID]` / `[ML-MODEL]` | Question, graph, summaries | Evidence-cited answer, confidence | F4, F5, F8 |
| F4 Implementation-check `[HYBRID]` | Spec/design, graph, predicates, QA, tests/traces | Clause verdict matrix | F6, F8, evaluation |
| F5 Bug-resolve `[HYBRID]` | Issue, F2, F4-style specs, gates | Patch proposal, certificate, risk report | F6, F8, F10 |
| F6 Patch-review `[HYBRID]` / `[ML-MODEL]` | Diff, graph, SARIF, tests, contracts | Merge/block recommendation, risk class | Release gates, F10 |
| F7 SAST repair `[HYBRID]` | SARIF alert, predicate examples, graph | Alert fix proposal and SARIF delta | F5, F6 |
| F8 Blast radius `[PY-CODE]` | Change set, graph, interfaces | Impact map | F5, F6, F4 |
| F9 Dynamic traces `[HYBRID]` | Reproduction, suspects, graph | Compressed runtime evidence | F2, F4, F5, F6 |
| F10 Memory `[PY-CODE]` / `[ML-MODEL]` | Prior trajectories and outcomes | Hints and rejected-memory notes | F2, F5, F6, F7 |
| F11 Operational harness `[PY-CODE]` | All workflow events, policies, budgets, monitors, gates, incidents | Run records, compliance verdicts, readiness scores, promotion candidates | All workflows, F10, evaluation, release gates |

### 4.15 What the pre-built index saves

| Without index | With pre-built index | Paper anchors |
|---|---|---|
| Re-parse entire repo set on every query | Parse once; query in milliseconds | `rig`, `repograph`, `codexgraph` |
| LLM embedding call per query | Vectors pre-stored; local similarity search | `fl-context-2026`, `repo-aware-kg` |
| Re-read files for context | Cached per-symbol summaries; only regenerated on file change | `reporepair`, `specrover` |
| `git blame` subprocess per query | Pre-indexed; instant lookup | `hafixagent` |
| Token-heavy raw file context in prompt | LLM receives graph slices and summaries only | `arise`, `locagent`, `repograph` |
| No cross-language visibility | `trace_cross_language` follows boundaries via all registered plugins | `rig`, `logiclens`, `eagle-x` |
| Monolithic scope | All tools/resources default to cross-language, cross-repo | `rig`, `logiclens`, `swe-polybench` |
| Static-analysis alerts live outside the agent | SARIF alerts are indexed, linked to graph nodes, and repairable through `run_sast_repair` / `sast-repair` | `predicatefix`, `codecureagent`, `securefixagent`, `nullrepair` |
| Patch review only says "looks correct" | Patch-risk classifier returns calibrated safe/overfit/vulnerable/vulnerability-introducing classes | `compass`, `pvbench`, `correct-not-safe`, `why-llms-fail-secpatch` |
| Re-learn same repair patterns repeatedly | Trajectory memory retrieves useful prior issue, FL, patch, and predicate patterns | `agent-her`, `evo-memory`, `c2f-grounded-memory` |
| Benchmark numbers drift or overfit silently | T1–T4 harness logs suite freshness, contamination canaries, and RDS v0.2 feature vectors | `swe-bench-live`, `swe-bench-illusion`, `swe-qa-pro`, `swe-rebench-v2` |
| Successful output cannot be audited after the fact | Run records preserve tool calls, approvals, evidence, budgets, gates, and incidents for replay and review | `agenttrace`, `aer`, `opendev` |
| Repeated failures stay anecdotal | Operational review promotes reviewed incidents into detectors, eval regressions, rules, policy, or schema-grounded memory | `schema-grounded-memory`, `agentic-harness-engineering`, `cqa` |

---

## 5. Evaluation, scoring, and release gates

The report's §14.3 evaluation harness is part of the architecture, not an afterthought. No feature is considered production-ready until it has a current harness run and its sub-metrics are stored under `code-intelligence://eval/{run_id}`.

**Mode mark:** the harness, benchmark adapters, metric computation, suite freshness logging, RDS feature extraction, calibration reports, and release-gate decisions are `[EVAL]` implemented as deterministic `[PY-CODE]`. The workflows under evaluation may use `[LLM]` / `[ML-MODEL]`, but scoring and gate decisions must be reproducible from stored artefacts.

**Build sequence:**

| Phase | Directions | Stop condition | Paper anchors |
|---|---|---|---|
| Phase 0 — Operational harness | Run records + harness-condition sheets + permission/tool policy + budget events + monitor alerts | Every workflow has replayable traces; unauthorized operations are denied or require approval; hard budget stops checkpoint instead of silently degrading evidence | `agenttrace`, `aer`, `opendev`, `runtime-governance`, `tokalator` |
| Phase 1 — Foundation | Control plane + static graph + eval harness | `swe-bench-live` baseline, top-1/top-3 FL metrics, graph build/update reliability | `swe-bench-live`, `fl-context-2026`, `arise`, `rig` |
| Phase 2 — Repair loop | Execution-free repair + patch-risk classifier | resolve-rate matches or beats `agentless` baseline; PoC⁺ pass-rate and risk-classifier ECE are logged | `agentless`, `specrover`, `agentic-code-reasoning`, `compass`, `pvbench` |
| Phase 3 — Implementation check and dynamics | implementation-check DAG + dynamic fallback | per-clause ECE ≤0.10 on Vul4J; dynamic-on-failure adds ≥5 pp resolve-rate at <2× compute | `kgacg`, `mids-valve`, `jml-autodoc`, `codespecbench`, `trace-prompt`, `daira`, `inspectcoder` |

**Internal benchmark ladder:**

| Tier | Frequency | Purpose | Suite | Time budget | Paper anchors |
|---|---|---|---|---|---|
| T1 Smoke | Every PR | Catch obvious regressions | 50 `swe-bench-live` lite instances + 20 PoC⁺ cases | <30 min | `swe-bench-live`, `pvbench` |
| T2 Regression | Nightly | Track resolve-rate and repo-QA trend | `swe-bench-live` lite + `swd-bench` Functionality-Localization subset | 4–8 h | `swe-bench-live`, `swd-bench`, `repo-path-retrieval-llm` |
| T3 Cross-language | Weekly | Catch language-specific drift | `swe-polybench` + `defects4c` | 12–24 h | `swe-polybench`, `defects4c`, `rig`, `logiclens` |
| T4 Implementation / spec | Per release | Accept implementation-check mode | `codespecbench` + Vul4J calibration set | release cadence | `codespecbench`, `why-llms-fail-secpatch`, `kgacg`, `mids-valve`, `jml-autodoc` |

**Mandatory reporting rules:**

- Use `swe-bench-live`, not SWE-bench Verified, as the headline resolve-rate; Verified remains useful only as a historical comparison.
- Refresh `swe-bench-live` monthly and log suite median age.
- Report PoC⁺ pass-rate alongside any vulnerability-class resolve-rate.
- Use `swd-bench` Functionality-Localization for repo-QA file-location acceptance; do not rely on LLM-as-judge scores.
- Report resolve-rate conditioned on correct FL so patch-generation gains are not confused with localisation gains.
- Log RDS v0.2 as a six-axis feature vector until the cross-benchmark regression is published.

**RDS v0.2 feature vector:**

| Axis | What gets logged | Why | Paper anchors |
|---|---|---|---|
| `files_touched` / localisation depth | files in the gold or proposed patch | basic repair scope | `fl-context-2026`, `swe-qa-pro` |
| `chain_depth` | longest relevant call/data-flow path | repository-level reasoning depth | `arise`, `rig`, `swe-qa-pro` |
| `cross_file_dataflow` | data-flow edges crossing file boundaries | multi-file coupling | `arise`, `rig`, `logiclens`, `swe-polybench` |
| `ambient_warning_load` | pre-patch SAST alerts in the closure | local risk/noise context | `predicatefix`, `codecureagent`, `securefixagent` |
| `test_brittleness` | fail/pass entropy under repeated or equivalent tests | flaky validation risk | `compass`, `pvbench`, `agent-coevo` |
| `memorisation_distance` | issue-text-only file-path accuracy gap on in-benchmark vs off-benchmark repos | contamination control from `swe-bench-illusion` | `swe-bench-illusion`, `swe-rebench-v2` |

**Operational harness gates:**

Harness-engineering adds release gates for the running tool itself. These gates measure whether results are auditable, policy-compliant, and improvable, not just whether a benchmark instance passed.

| Gate | Required signal | Blocks when | Paper anchors |
|---|---|---|---|
| Trace completeness | ≥99% of workflow runs have `session_start`, harness condition, stage events, tool events, gate events, final verdict, and retention/redaction metadata | Any release workflow can produce an unreviewable verdict | `agenttrace`, `aer` |
| Policy compliance | 0 unauthorized writes, 0 unapproved high-risk executes, 0 missing required approvals in T1/T2 and production canary runs | A process-noncompliant run is counted as failure even if tests pass | `runtime-governance`, `alara`, `opendev` |
| Budget reliability | Token/tool/wall-clock budgets are logged; hard-stop/checkpoint behaviour works; retry storms are detected | Budget exhaustion can silently degrade evidence quality | `tokalator`, `opendev` |
| Maintainability oracle | F6 patch-review and F5 bug-resolve run structural checks for non-trivial diffs | Behaviour-correct patches violate dependency direction, responsibility boundaries, testability, or side-effect isolation | `needle-repo` |
| Prompt/manifest regression | Tool descriptions, workflow prompts, and policy/manifests pass visible/hidden/mutation/spec-evolution tests before becoming default | Governance wording changes silently weaken tool order, refusal, or data policy | `tdad` |
| Harness drift and monotonicity | `classify_harness_drift` is clean or reviewed; no `relaxed` artefacts; readiness axes do not regress without approved incident/waiver evidence | Hard constraints are removed, runtime overlays widen permissions, a stage is skipped, or readiness drops silently | `opendev`, `workstream`, `tdad`, `agentic-harness-engineering` |
| Readiness threshold | `compute_readiness_score(repo)` meets the configured threshold for the requested autonomy level | Repo lacks runnable tests, SAST, docs/spec links, policy coverage, or sandboxable commands | `workstream`, `opendev` |
| Incident closure | P0/P1 incidents have containment, root cause, remediation, evidence links, and detector/eval follow-up before release | Known unsafe failure mode has no regression guard | `aer`, `agentfixer`, `cqa` |

**Operational quality metrics:**

| Metric | Definition |
|---|---|
| `process_compliance_rate` | Runs with required stages, permissions, gates, and records divided by total runs |
| `trace_replay_success_rate` | Runs whose final verdict can be reconstructed from stored events and artefacts |
| `human_review_actionability` | Reviewer decisions that cite concrete evidence/gates rather than free-form model claims |
| `incident_recidivism_rate` | Repeated incidents from the same root cause after remediation |
| `promotion_precision` | Promoted memories/rules/evals later judged useful and non-harmful |
| `cost_per_accepted_verdict` | Tokens + tool time + wall time per verdict that passes code and operational gates |
| `readiness_delta` | Repository readiness score change after recommended readiness tasks are completed |

These metrics are reported beside T1–T4 benchmark metrics. A model or algorithm change is not considered an improvement if it raises resolve-rate while lowering trace replay, policy compliance, or incident rate beyond configured tolerance.

---

## 6. Research paper anchors

Each design decision traces back to one or more papers in the source research report. This mapping is preserved here for detailed feature design work. Paper slugs in this table are resolved in the citation registry below; follow-on design notes should cite the registry entry rather than copying informal slug names alone.

| Design decision | Paper(s) | Report section |
|---|---|---|
| Repository call graph as foundational substrate | `arise`, `locagent`, `cosil`, `codexgraph`, `repograph`, `repo-aware-kg` | §7 A |
| Cross-language repository graph (polyglot typed-edge schema) | `rig`, `logiclens`, `eagle-x` | §7 A / §13.3 |
| Build/test evidence is part of the graph, not separate CI metadata | `rig`, `swe-polybench` | §13.3 / §14.2.3 |
| Structured AST-aware issue-resolution tool APIs and SBFL priors | `autocoderover`, `agentless` | §6 Control / §8 B |
| Cheap mostly-static open-model repair baseline | `swe-fixer` | §8 B |
| File-level fault localisation gives 15–17× repair improvement | `fl-context-2026` | §6 Control |
| LLM-ranked retrieval beats BM25 and rule-based retrieval | `fl-context-2026` | §6 Control |
| Per-candidate reasoning chains for FL ranking (RGFL pattern) | `rgfl` | §7 A |
| LLM-compressed runtime traces beat raw trace dumps | `trace-prompt` | §6 Control |
| Scope-filtered structured dynamic traces and debugger-guided inspection | `daira`, `tracerepair`, `inspectcoder` | §10 D |
| Git blame chain as a near-free FL signal | `hafixagent` | §8 B |
| Hierarchical LLM summaries as the repo knowledge index | `reporepair` | §8 B |
| Patch + pre/post-condition spec shipped together | `specrover` | §6 Control |
| Execution-free certificate verification (88.8% accuracy) | `agentic-code-reasoning` | §9 C |
| 4-agent parallel safety check (+39.7pp over single agent) | `multi-agent-info-theory` | §9 C |
| Patch correctness ≠ patch safety (adversarial patch analysis) | `correct-not-safe`, `redteam-apr` | §9 C |
| Design/spec → implementation fulfilment loop (Gap 1 **bridged** by `kgacg` + `mids-valve` + `jml-autodoc`; assembly is engineering) | `kgacg`, `mids-valve`, `jml-autodoc` | §13.1 |
| LSP as language-agnostic code navigation backend | `marscode` | §8 B |
| Best LLM achieves only 20.2% on repo-level spec tasks | `codespecbench` | §6 Control |
| Predicate-driven retrieval (negate rule predicate → fix-knowledge examples) | `predicatefix` | §12 theme 10.8 / §8 B |
| Repo-level QA: file-localisation ~91% EM with fine-tuned model | `repo-path-retrieval-llm` | §13.6 |
| Repo-level QA: cross-file behaviour-tracing 40–60%; Graph-RAG +6pp | `swe-qa`, `coreqa`, `beyond-code-snippets`, `repochat` | §12 theme 10.7 / §13.6 |
| Seven-stage implementation-check DAG: design/spec intent → ontology → contract → graph → static/dynamic verdict → calibrated aggregation | `kgacg`, `mids-valve`, `jml-autodoc`, `predicatefix`, `agent-coevo`, `swe-qa` | §13.1 |
| Issue-anchored reproduction tests and pass-then-invert bug reproduction | `issue2test`, `assertflip` | §9 C |
| Buildable operational loop: SARIF alert → graph slice → spec/test → patch → SAST/build re-check | `predicatefix`, `locagent`, `agent-coevo`, `codecureagent` | §13.7 |
| Static-analysis alerts as patch trigger (distinct from failing-test trigger) | `predicatefix`, `llm4cve`, `logiceval` | §12 theme 10.8 / §8 B |
| Survey: 4-paradigm × {RAG, AAG} design space for repair systems | `survey-yang-2025` | §6 Control |
| Survey: 175 papers — reward design, scaffold taxonomy, efficiency gaps | `survey-issue-resolution-2026` | §6 Control |
| Patch-class risk classifier training data and harness | `compass`, `pvbench`, `logiceval`, `why-llms-fail-secpatch` | §13.2 |
| >40% of "correct" patches fail PoC⁺ tests — patch safety gate | `pvbench` | §8 B / §13.2 |
| SWE-bench overfitting: 19.25% live vs. 43.20% static (use live as headline) | `swe-bench-live` | §11 E |
| T1–T4 internal evaluation ladder and repo-QA acceptance | `swe-bench-live`, `swd-bench`, `swe-polybench`, `defects4c`, `codespecbench` | §14.3 |
| Memorisation contamination: in-benchmark file-path-from-issue accuracy 76% vs. 53% off-benchmark — adds `memorisation_distance` as RDS v0.2's sixth axis; never report SWE-bench Verified as the headline metric | `swe-bench-illusion` | §13.4 |
| RDS v0.2 — six-axis instance-difficulty score (Gap 4, still academic); calibration-by-baseline-residual × multi-axis aggregation × 32 k+ multilingual corpus; log axes as per-instance feature vector in the §14.3 eval harness until the cross-benchmark regression is published | `swe-qa-pro`, `livecoder`, `swe-rebench-v2` | §13.4 |
| SARIF v2.1.0 as the analyser-data lingua franca for the SAST loop | `codecureagent`, `securefixagent`, `nullrepair`, `codeql-rule-multiagent`, `predicatefix` | §13.7 |
| Memory & experience replay: hindsight relabelling, eviction, and misalignment guard | `agent-her`, `evo-memory`, `memory-management-empirical`, `graph-memory-rl`, `c2f-grounded-memory` | §13.5 |
| Live operational trace and append-only run record for every workflow | `agenttrace`, `aer`, `opendev` | Harness-engineering overlay §4-§6 |
| Harness-condition sheet required for benchmark and production comparability | `harness-native-se`, `opendev`, `workstream` | Harness-engineering overlay §7 / Appendix C |
| Structural least-privilege tool DAG and deny-first permission policy | `alara`, `runtime-governance`, `opendev` | Harness-engineering overlay §5 |
| Context/cost budgets, staged compaction, and budget events as correctness signals | `tokalator`, `opendev` | Harness-engineering overlay §5.4 / guide §9 |
| Cumulative run/session monitoring, anomaly detection, and incident review | `cqa`, `agentfixer`, `agent-drift`, `aer` | Harness-engineering overlay §7 / guide §11 |
| Maintainability oracles in patch-review beyond functional tests | `needle-repo` | Harness-engineering overlay §5.11 / guide §6.6 |
| Repository readiness score before higher-autonomy workflows | `workstream` | Harness-engineering overlay §5.11 / guide §7.5 |
| Prompt, tool-description, and manifest regression tests | `tdad` | Harness-engineering overlay §6.1 / guide §4.7 |
| Schema-grounded operational memory and reviewable lesson promotion | `schema-grounded-memory`, `ama-bench`, `agentic-harness-engineering` | Harness-engineering overlay §5.6 / guide §8.5 |

### 6.1 Citation registry

Citation levels:
- `bib:*` means the citation exists in `llm-based-static-code-analysis.bib`.
- `arXiv:*` / `S2:*` means the citation is currently carried by the source research report, often as an abstract-grade bridge card. Promote those entries into BibTeX before using them in external publications.

| Anchor | Citation / source |
|---|---|
| `aer` | "Agent Execution Record / AER," arXiv:2603.21692, 2026. Source harness-engineering report §5.2 and Appendix C. |
| `agent-drift` | "Agent Drift," arXiv:2601.04170, 2026. Source harness-engineering report §4/§5. |
| `agentfixer` | "AgentFixer," arXiv:2603.29848, 2026. Source harness-engineering report §4/§10 and guide §11. |
| `agentic-harness-engineering` | "Agentic Harness Engineering," arXiv:2604.25850, 2026. Source harness-engineering report §5.11 and guide §2.2. |
| `agenttrace` | "AgentTrace," arXiv:2602.10133, 2026. Source harness-engineering report §5.2 and guide §2.1. |
| `alara` | "ALARA: As Low As Reasonably Achievable tool access for agents," arXiv:2603.20380, 2026. Source harness-engineering report §5.5. |
| `ama-bench` | "AMA-Bench / tool-augmented memory with causality graph," arXiv:2602.22769, 2026. Source harness-engineering report §5.6. |
| `agentless` | Xia, Deng, Dunn, and Zhang, "Agentless: Demystifying LLM-based Software Engineering Agents," arXiv:2407.01489, 2024. `bib:xia2024agentless` |
| `agent-coevo` | Li et al., "Beyond Fixed Tests: Repository-Level Issue Resolution as Coevolution of Code and Behavioral Constraints," arXiv:2604.04580, 2026. `bib:li2026beyond` |
| `agent-her` | "Hindsight Experience Replay," arXiv:2603.21357, 2026. Source report §13.5 abstract-grade card. |
| `agentic-code-reasoning` | Ugare and Chandra, "Agentic Code Reasoning," arXiv:2603.01896, 2026. `bib:ugare2026agentic` |
| `arise` | Seddik and Fard, "ARISE: A Repository-level Graph Representation and Toolset for Agentic Fault Localization and Program Repair," arXiv:2605.03117, 2026. `bib:seddik2026arise` |
| `assertflip` | "AssertFlip: Reproducing Bugs via Inversion of LLM-Generated Passing Tests," arXiv:2507.17542, 2025. Source report §9 C card. |
| `autocoderover` | "AutoCodeRover: Autonomous Program Improvement," arXiv:2404.05427, ISSTA 2024. Source report §6 Control / §8 B card. |
| `beyond-code-snippets` | "Beyond Code Snippets: Benchmarking LLMs on Repository-Level Question Answering," arXiv:2603.26567, FSE 2026. Source report §11 E card. |
| `c2f-grounded-memory` | "Coarse-to-fine Grounded Memory," arXiv:2508.15305, 2025. Source report §13.5 abstract-grade card. |
| `codecureagent` | "CodeCureAgent," arXiv:2509.11787, 2025. Source report §13.7 abstract-grade card. |
| `codeql-rule-multiagent` | "CodeQL Rule Multiagent," Semantic Scholar `s2-a66952f380`, 2026. Source report §13.7 abstract-grade card. |
| `codespecbench` | Chen et al., "CodeSpecBench: Benchmarking LLMs for Executable Behavioral Specification Generation," arXiv:2604.12268, 2026. `bib:chen2026codespecbench` |
| `codexgraph` | "CodexGraph: LLM Agents over Neo4j Code Graphs," arXiv:2408.03910, 2024. Source report §7 A card. |
| `compass` | "ComPass: Contrastive Learning for Automated Patch Correctness Assessment," arXiv:2602.07561, Empirical Software Engineering. Source report §13.2 card. |
| `coreqa` | "CoReQA: Uncovering Potentials of Language Models in Code Repository Question Answering," arXiv:2501.03447, 2025. Source report §11 E card. |
| `correct-not-safe` | "When \"Correct\" Is Not Safe: Trust Functionally Correct Patches by Code Agents?," arXiv:2510.17862, 2025. Source report §9 C card. |
| `cosil` | Jiang et al., "CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching," arXiv:2503.22424, 2025. `bib:jiang2025cosil` |
| `cqa` | "Salami Slicing / Cumulative Query Audit," arXiv:2604.11309, 2026. Source harness-engineering report §5.11 and guide Appendix B. |
| `daira` | Liu et al., "Dynamic analysis enhances issue resolution," arXiv:2603.22048, 2026. `bib:liu2026dynamic` |
| `defects4c` | "Defects4C: Benchmarking LLM Repair Capability with C/C++ Bugs," arXiv:2510.11059, 2025. Source report §11 E card. |
| `eagle-x` | "EAGLE-X," Semantic Scholar `s2-072e38a20f`, 2025. Source report §13.3 abstract-grade card. |
| `evo-memory` | "Evo-Memory," arXiv:2511.20857, 2025. Source report §13.5 abstract-grade card. |
| `fl-context-2026` | Sepidband, Pham, and Hemmati, "On the Role of Fault Localization Context for LLM-Based Program Repair," arXiv:2604.05481, 2026. `bib:sepidband2026flcontext` |
| `graph-memory-rl` | "Graph Memory RL," arXiv:2511.07800, 2025. Source report §13.5 abstract-grade card. |
| `hafixagent` | "HAFixAgent: History-Aware Automated Program Repair Agent," arXiv:2511.01047, 2025. Source report §8 B card. |
| `harness-native-se` | "Harness-Native Software Engineering," scholar source carried by the harness-engineering report; source report §11.2 / Appendix C. |
| `inspectcoder` | "InspectCoder: Interactive LLM-Debugger Self-Repair," arXiv:2510.18327, 2025. Source report §10 D card. |
| `issue2test` | "Issue2Test: Generating Reproducing Test Cases from Issue Reports," arXiv:2503.16320, 2026. Source report §9 C card. |
| `jml-autodoc` | "Formal Methods Meets Readability," arXiv:2506.09230, 2025. Source report §13.1 abstract-grade card. |
| `kgacg` | "Knowledge-Guided Application-Level Code Generation," arXiv:2510.19868, 2025. Source report §13.1 abstract-grade card. |
| `livecoder` | "Persistent Cross-Attempt State Optimization for Repository-Level Code Generation," arXiv:2604.03632, 2026. Source report §13.4 abstract-grade card. |
| `llm4cve` | "LLM4CVE: Enabling Iterative Automated Vulnerability Repair with LLMs," arXiv:2501.03446, 2025. Source report §8 B card. |
| `locagent` | Chen et al., "LocAgent: Graph-Guided LLM Agents for Code Localization," arXiv:2503.09089, 2025. `bib:chen2025locagent` |
| `logiceval` | "LogicEval: A Systematic Framework for Evaluating Automated Repair Techniques for Logical Vulnerabilities," arXiv:2604.12994, ACL 2026. Source report §11 E card. |
| `logiclens` | "LogicLens," arXiv:2601.10773, 2026. Source report §13.3 abstract-grade card. |
| `marscode` | "MarsCode Agent: AI-native Automated Bug Fixing," arXiv:2409.00899, 2024. Source report §8 B card. |
| `memory-management-empirical` | "Empirical Study of Memory Addition/Deletion," arXiv:2505.16067, 2025. Source report §13.5 abstract-grade card. |
| `mids-valve` | "Machine-Interpretable Engineering Design Standards," arXiv:2510.01736, 2025. Source report §13.1 abstract-grade card. |
| `multi-agent-info-theory` | "Multi-Agent Code Verification via Information Theory," arXiv:2511.16708, 2025. Source report §9 C card. |
| `needle-repo` | "Needle in the Repo," arXiv:2603.27745, 2026. Source harness-engineering report §5.11 and guide §6.6. |
| `nullrepair` | "NullRepair," arXiv:2507.20674, 2025. Source report §13.7 abstract-grade card. |
| `opendev` | "OpenDev," arXiv:2603.05344, 2026. Source harness-engineering report §5.11 and guide §2.2. |
| `predicatefix` | "PredicateFix: Repairing Static Analysis Alerts with Bridging Predicates," arXiv:2503.12205, ICSE 2026. Source report §8 B / §13.7 card. |
| `pvbench` | "Patch Validation in Automated Vulnerability Repair," arXiv:2603.06858, 2026. Source report §13.2 abstract-grade card. |
| `redteam-apr` | "Incoherence as Oracle-less Measure of Error in LLM-Based Code Generation," arXiv:2507.00057, AAAI 2026. Source report §9 C card; roster label mismatch noted there. |
| `repo-aware-kg` | "KGCompass: Repository-Aware Knowledge Graph for Repair," arXiv:2503.21710, 2025. Source report §7 A card. |
| `repo-path-retrieval-llm` | "Fine-tuned LLM for Repo Path Retrieval," arXiv:2510.08850, 2025. Source report §13.6 abstract-grade card. |
| `repochat` | "RepoChat," Semantic Scholar `s2-d026611e1b`, 2025. Source report §13.6 abstract-grade card. |
| `repograph` | Ouyang et al., "RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph," arXiv:2410.14684, ICLR 2025. `bib:ouyang2024repograph` |
| `reporepair` | Pan et al., "RepoRepair: Leveraging Code Documentation for Repository-Level Automated Program Repair," arXiv:2603.01048, 2026. `bib:pan2026reporepair` |
| `rgfl` | Sepidband et al., "RGFL: Reasoning Guided Fault Localization for Automated Program Repair Using Large Language Models," arXiv:2601.18044, 2026. `bib:sepidband2026rgfl` |
| `rig` | "Repository Intelligence Graph," arXiv:2601.10112, 2026. Source report §13.3 abstract-grade card. |
| `runtime-governance` | "Runtime Governance," arXiv:2604.07833, 2026. Source harness-engineering report §5.5 and guide Appendix B. |
| `saver` | "SAVER," arXiv:2604.08401, 2026. Source harness-engineering report §5.3 / guide §6. |
| `schema-grounded-memory` | "Schema-Grounded Memory," arXiv:2604.27906, 2026. Source harness-engineering report §5.11 and guide §8.5. |
| `securefixagent` | "SecureFixAgent," arXiv:2509.16275, 2025. Source report §13.7 abstract-grade card. |
| `severa` | "SEVerA," arXiv:2603.25111, 2026. Source harness-engineering report §5.3 / guide §6. |
| `specrover` | Ruan, Zhang, and Roychoudhury, "SpecRover: Code Intent Extraction via LLMs," arXiv:2408.02232, ICSE. `bib:ruan2024specrover` |
| `survey-issue-resolution-2026` | "Advances and Frontiers of LLM-based Issue Resolution in Software Engineering: A Comprehensive Survey," arXiv:2601.11655, 2026. Source report §6 Control card. |
| `survey-yang-2025` | Yang et al., "A Survey of LLM-based Software Repair: Taxonomies, Design Paradigms, and Applications," arXiv:2506.23749, TOSEM 2025. `bib:yang2025aprsurvey` |
| `swd-bench` | "SWD-Bench," arXiv:2604.06793, 2026. Source report §13.6 abstract-grade card. |
| `swe-bench-illusion` | "The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason," arXiv:2506.12286, 2025. Source report §13.4 abstract-grade card. |
| `swe-bench-live` | Zhang et al., "SWE-bench Goes Live!," arXiv:2505.23419, 2025. `bib:zhang2025swebenchlive` |
| `swe-fixer` | "SWE-Fixer: Training Open-Source LLMs for Effective and Efficient GitHub Issue Resolution," arXiv:2501.05040, 2025. Source report §8 B card. |
| `swe-polybench` | "SWE-PolyBench," arXiv:2504.08703, 2025. Source report §13.3 abstract-grade card. |
| `swe-qa` | "SWE-QA: Can Language Models Answer Repository-level Code Questions?," arXiv:2509.14635, 2025. Source report §11 E card. |
| `swe-qa-pro` | "A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding," arXiv:2603.16124, 2026. Source report §13.4 abstract-grade card. |
| `swe-rebench-v2` | "Language-Agnostic SWE Task Collection at Scale," arXiv:2602.23866, 2026. Source report §13.4 abstract-grade card. |
| `trace-prompt` | Haque et al., "Towards Effectively Leveraging Execution Traces for Program Repair with Code LLMs," arXiv:2505.04441, 2025. `bib:haque2025traceprompting` |
| `trace-level-comparison` | "Trace-Level Behavioral Comparison," arXiv:2604.07929, 2026. Source harness-engineering report §5.2. |
| `tracerepair` | Wu et al., "Runtime Execution Traces Guided Automated Program Repair with Multi-Agent Debate," arXiv:2604.02647, 2026. `bib:wu2026runtime` |
| `tdad` | "TDAD: Test-Driven Agent Description / prompt and tool-description regression," arXiv:2603.08806, 2026. Source harness-engineering report §5.11 and guide §4.7. |
| `tokalator` | "Tokalator," arXiv:2604.08290, 2026. Source harness-engineering report §5.4 and guide §9. |
| `workstream` | "Workstream," arXiv:2604.17055, 2026. Source harness-engineering report §5.11 and guide §7.5. |
| `why-llms-fail-secpatch` | "Why LLMs Fail at Security Patch Generation," arXiv:2603.10072, 2026. Source report §13.2 abstract-grade card. |
