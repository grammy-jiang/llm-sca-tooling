# Architecture Overview

> This document describes the five product surfaces, the evidence hierarchy,
> the phase dependency map, and the key design constraints of `evidence-sca`.
> For operational setup, see [Harness Setup Guide](harness-setup-guide.md).

---

## Limitations

- `evidence-sca` augments, not replaces, human code review. Findings are graded by
  evidence type; only `parser`-grade findings carry high confidence.
- LLM reasoning is applied **after** typed evidence is gathered, not instead of it.
  A workflow that cannot gather evidence falls back to `heuristic` or `unknown` grade.
- The tool does not modify source code. It produces reports, risk grades, and
  `HarnessConditionSheet` artefacts; humans decide on remediation.
- Every quality claim in this document references Phase 18 calibration reports.
  Performance numbers are from the evaluation harness benchmarks, not from
  production deployments.
- A `HarnessConditionSheet` must be completed for every release or evaluation run.

---

## Five Product Surfaces

```
┌─────────────────────────────────────────────────────┐
│  1. MCP Server                                      │
│     35 tools · 14 resources · 12 prompts            │
│     stdio and Streamable HTTP transports            │
├─────────────────────────────────────────────────────┤
│  2. Workflow Orchestrator                           │
│     Bug resolve · Patch review · SAST repair        │
│     Implementation check · Fault localisation       │
├─────────────────────────────────────────────────────┤
│  3. Evaluation Harness                              │
│     T1-T4 benchmark ladder · RDS v0.2 features      │
│     Calibration reports · Contamination canaries    │
├─────────────────────────────────────────────────────┤
│  4. Operational Harness Plane                       │
│     Run records · Incident tracking · Trajectory    │
│     memory · Operational review · Release gate      │
├─────────────────────────────────────────────────────┤
│  5. Operational Guardrails                          │
│     Permission profiles · Cumulative risk monitor   │
│     Harness drift checks · Privacy controls         │
│     Trace redaction audit · Session replay          │
└─────────────────────────────────────────────────────┘
```

### 1. MCP Server

The MCP server is the primary integration surface. It exposes:

- **Tools**: callable functions (graph build, workflow execution, memory retrieval, etc.)
- **Resources**: read-only data mounts (graph slices, governance manifests, incident records)
- **Prompts**: pre-built workflow templates for LLM clients

The server starts in stdio mode (default, compatible with all MCP clients) or
Streamable HTTP mode (for multi-client / remote deployments).

### 2. Workflow Orchestrator

Each workflow (bug resolve, patch review, etc.) follows the same pattern:

1. Gather typed evidence from the code graph, SARIF data, and test corpus.
2. Grade evidence: `parser > analyser > heuristic > unknown`.
3. Invoke LLM reasoning only on evidence-graded context.
4. Produce a structured report with confidence-qualified findings.
5. Record a `RunRecord` and `HarnessConditionSheet`.

### 3. Evaluation Harness

The evaluation harness validates workflow quality against four benchmark tiers:

| Tier | Description | Mode |
|---|---|---|
| T1 | Smoke eval — synthetic fixtures | null-mode (no LLM) |
| T2 | Unit eval — published benchmarks (SWE-bench-Live style) | null + LLM |
| T3 | Integration eval — cross-language fixtures | LLM required |
| T4 | Production eval — live repositories | LLM + human review |

T1 runs in null-mode and is the minimum gate for every CI check.

### 4. Operational Harness Plane

The operational harness plane persists all run artefacts:

- **RunRecord**: event log, gate results, budget consumption
- **IncidentRecord**: P0/P1/P2 incidents with timeline and remediation
- **TrajectoryMemory**: promoted lessons for experience replay
- **OperationalReview**: aggregated session analysis

### 5. Operational Guardrails

Guardrails enforce governance constraints at runtime:

- **Permission profiles**: six modes (read_only → commit) with explicit capability grants
- **Cumulative risk monitor**: detects doom-loops, budget exhaustion, and suspicious multi-step patterns
- **Harness drift checker**: detects AGENTS.md relaxation, missing CI gates, stale tool descriptions
- **Privacy controls**: redaction, retention classes, right-to-delete pipeline
- **Trace redaction audit**: sample-checks stored traces for unredacted secrets

---

## Evidence Hierarchy

All findings are graded by the evidence type that produced them:

| Grade | Source | Confidence |
|---|---|---|
| `parser` | ctags AST, language server, SARIF exact location | High |
| `analyser` | dataflow analysis, cross-file call graph | Medium-high |
| `heuristic` | pattern matching, keyword search, import graph | Medium |
| `unknown` | LLM reasoning without graph evidence | Low |

The tool **never** upgrades evidence grade; it can only downgrade if evidence is
contradicted by a higher-grade source.

---

## Phase Dependency Map

```
H0  Harness Foundation
│
├─ Ph0  Python Package Skeleton
│  ├─ Ph1  Shared Schemas and Evidence Model
│  ├─ Ph2  Local Graph Store and Repository Registry
│  │  └─ Ph3  Repository Indexing MVP
│  │     └─ Ph4  MCP Server Core
│  │        ├─ Ph5  Language Backend Expansion
│  │        ├─ Ph6  SARIF and Static Analysis Layer
│  │        │  └─ Ph7  Cross-Language Plugin System
│  │        ├─ Ph8  Repository QA MVP
│  │        │  └─ Ph9  Fault Localisation
│  │        │     └─ Ph10 Evaluation Harness Baseline
│  │        │        ├─ Ph11 Patch Review and Risk Gates
│  │        │        ├─ Ph12 SAST Alert Repair
│  │        │        ├─ Ph13 Bug-Resolve Workflow
│  │        │        ├─ Ph14 Implementation Check
│  │        │        ├─ Ph15 Blast Radius
│  │        │        ├─ Ph16 Dynamic Trace Augmentation
│  │        │        ├─ Ph17 Trajectory Memory
│  │        │        └─ Ph18 Full Calibration and Release Gates
│  │        │           └─ Ph19 Operational Hardening (this phase)
```

---

## Key Design Constraints

1. **Typed evidence first, LLM second.** Every workflow gathers graph/SARIF/test evidence
   before invoking LLM reasoning. Evidence grade determines confidence in the output.

2. **No silent failures.** Every tool call either produces evidence-graded output or
   explicitly returns `unknown` grade with a reason.

3. **Operational transparency.** Every run produces a `RunRecord` that can be replayed
   from the operational store without access to the source repository.

4. **Governance by default.** Permission profiles, budget limits, and drift checks are
   active in every run. They cannot be disabled without a reviewed waiver.

5. **HC1-HC6 are unconditional.** Hard constraints (no secrets, no out-of-scope writes,
   destructive operations require approval, no autonomous migrations, deny-by-default
   network, no red-class data in prompts) are never relaxed.

---

## How to Read a HarnessConditionSheet

A `HarnessConditionSheet` is the acceptance artefact for every evaluation and release run.
It records:

- `harness_condition_id`: unique identifier
- `run_id`: the associated run record
- `permission_profile`: the active permission mode
- `gates_passed`: list of deterministic gates (verify, SAST, lint, tests)
- `eval_tier`: T1-T4
- `null_mode`: whether LLM was used
- `calibration_report_ref`: reference to Phase 18 calibration results
- `verdict`: `pass | fail | inconclusive`

A run without a completed `HarnessConditionSheet` is **not accepted as evidence**
of quality or correctness.

---

## Related Documents

- [Installation Guide](installation.md)
- [Quickstart Guide](quickstart.md)
- [Harness Setup Guide](harness-setup-guide.md)
- [Evaluation Guide](evaluation-guide.md)
- [Plugin Authoring Guide](plugin-authoring-guide.md)
- [Incident Response Guide](incident-response-guide.md)
