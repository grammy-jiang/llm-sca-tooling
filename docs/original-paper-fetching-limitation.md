# Original Paper Fetching Limitation

## What Happened

During the implementation-completeness audit, the repository was checked against
the local architecture and research materials:

- `docs/llm-sca-tooling-architecture.md`
- `docs/llm-based-static-code-analysis-research-report.md`
- repository-local workflow skills under `.skills/` and harness skills under
  `.agent/skills/`
- the repository's own `code-intelligence` MCP server
- local tests and verification gates

The audit did not retrieve and re-read the original external papers cited by the
research report. As a result, the method-coverage matrix is primarily a
local-source audit, not a fresh paper-by-paper reproduction audit.

A later retry checked the local research-pipeline workspace at
`/home/grammy-jiang/Documents/Research/static-code-analysis`. That workspace
does contain converted paper Markdown for some relevant papers and shortlist
metadata for several others. This means no raw-PDF reading is needed for those
available papers, but the original implementation matrix should still be treated
as research-report-backed unless a row explicitly cites converted-paper
Markdown.

This is acceptable for the first implementation audit because the local research
report already contains the relevant ideas, methodology summaries, gap closure
protocols, evaluation targets, and caveats needed to compare the repository
against the intended design.

## Why It Happened

The repository policy in `AGENTS.md` sets network egress to deny-by-default under
HC5. The current execution environment also has restricted network access. The
available `research-pipeline` skill is intended for literature retrieval, paper
screening, PDF download/conversion, Markdown extraction, summarization, and
evidence-cited report generation, but using it to fetch missing original papers
would require approved network/data access.

Because no task-specific network exception was documented or approved, the
initial audit used only local repository evidence. This avoided violating the
repository's hard constraints, but it means the audit cannot claim that every
original paper was independently fetched, read, and mapped to implementation
details.

No agent should manually read raw PDFs as the normal path. When original-paper
detail is needed, the intended path is:

1. let `research-pipeline` retrieve/download the paper;
2. let `research-pipeline` convert the paper to Markdown;
3. review the converted Markdown and extracted evidence;
4. cite the converted-paper evidence in the implementation matrix.

## Impact

The current implementation matrix can support these claims:

- The repository implements or partially implements surfaces described by the
  local architecture document.
- The repository has method coverage that can be compared against the local
  research report.
- Remaining gaps are tracked at the level of methods and expected capabilities.

The current matrix cannot yet support these stronger claims:

- Every original paper cited by the research report was re-fetched.
- Every paper's exact algorithm, dataset, metric, and failure mode was checked
  against code.
- The implementation was reproduced against the original paper evaluation setup.

## Next Step To Fix This

1. Use the local research report first.

   Before attempting paper retrieval, inspect
   `docs/llm-based-static-code-analysis-research-report.md`. For most current
   implementation checks it already provides enough methodology detail:
   method summaries, paper anchors, implementation glue designs, measurable
   gates, and known caveats.

2. Mark the specific rows that need paper-level detail.

   Original-paper Markdown should be read only when the local report lacks one
   of these items:

   - exact algorithm steps needed for implementation;
   - exact dataset split or benchmark protocol;
   - exact metric definition or calibration procedure;
   - caveats that affect whether a feature should be claimed as implemented;
   - reproduction details needed for an acceptance gate.

3. Check the local research-pipeline workspace before requesting network/data
   access.

   Converted artifacts may already exist under
   `/home/grammy-jiang/Documents/Research/static-code-analysis/runs/`. If the
   needed paper exists there as Markdown, review that artifact first and record
   the path in the implementation matrix.

4. Create a task-specific network/data approval record only for papers that are
   not already available locally.

   The record should identify the allowed sources, expected outputs, and
   retention policy. Recommended allowed sources are arXiv, Semantic Scholar,
   OpenAlex, DBLP, ACM/IEEE pages where accessible, GitHub repositories linked
   by the papers, and official benchmark pages.

5. Run the `research-pipeline` workflow for only the needed papers.

   The workflow should fetch paper metadata, download accessible papers, convert
   them to Markdown, extract method claims, extract evaluation requirements, and
   write a cited paper-audit report. Agents should review the Markdown and
   extraction artifacts, not raw PDFs.

6. Replace local-report-only rows with paper-backed rows where needed.

   Update `docs/research-method-implementation-matrix.md` so each row includes:

   - paper identifier and citation
   - method claim
   - required algorithm or system component
   - required dataset or benchmark
   - required metric or calibration gate
   - implementation files
   - test evidence
   - status: implemented, partial, stub, missing, or out-of-scope

7. Add reproduction tasks for methods with measurable gates.

   Examples:

   - FL-context localization and repair-lift evaluation
   - patch-risk classifier macro-F1 and ECE calibration
   - repo-QA behavior benchmark accuracy
   - SAST repair analyzer-rerun and SARIF-delta validation
   - memory/replay A/B evaluation at constant context budget

8. Keep academic/open problems explicitly separated from product gaps.

   Gap 4, repository difficulty scoring, is still identified as academic in the
   local research report. The next audit should not mark it as fully implemented
   unless there is benchmark-backed evidence that the score predicts difficulty
   across repositories and task suites.

## Acceptance Criteria

The original-paper audit is complete only when:

- each cited paper has a source record or a documented retrieval failure;
- each method claim is mapped to concrete code, tests, and MCP/tool surfaces;
- each claimed metric has local reproduction evidence or is marked unavailable;
- `docs/research-method-implementation-matrix.md` distinguishes paper-backed
  evidence from local-report inference;
- any external data or network use is recorded in the harness condition sheet or
  equivalent operational evidence.

## Current Status

The local research report appears sufficient for the current matrix-level
implementation audit. It includes:

- the seven research gaps and their closure status;
- the engineering glue designs for design-doc audit, patch-risk classification,
  cross-language graphing, memory/replay, repo-QA, and SAST repair;
- concrete evaluation gates such as ECE, macro-F1, top-k localization, PoC+
  pass rate, SARIF delta, and memory A/B thresholds;
- a list of abstract-grade cards that should be promoted to full reads when
  deeper implementation or reproduction work begins.

The next original-paper reads should therefore be targeted, not blanket reads.
The first candidates are the report's own "promote to full reads" list:
`kgacg`, `pvbench`, `rig`, `agent-her`, `swd-bench`, `codecureagent`,
`swe-bench-illusion`, and `swe-rebench-v2`.

No converted-paper Markdown artifacts were found inside this repository during
the initial check. A retry found a separate local research-pipeline workspace at
`/home/grammy-jiang/Documents/Research/static-code-analysis` with converted
Markdown for these relevant papers:

| Method area | Paper ID | Local converted Markdown |
|---|---|---|
| SWE-Bench memorization / RDS evidence | `2506.12286` | `/home/grammy-jiang/Documents/Research/static-code-analysis/runs/comprehensive/convert/2506.12286.md` |
| ComPass patch correctness / patch-risk evidence | `2602.07561` | `/home/grammy-jiang/Documents/Research/static-code-analysis/runs/comprehensive/convert2/2602.07561.md` |
| PredicateFix SAST repair evidence | `2503.12205` | `/home/grammy-jiang/Documents/Research/static-code-analysis/runs/comprehensive/convert2/2503.12205.md` |

The same workspace also has shortlist metadata, but no converted Markdown was
found by paper ID, for these targeted gap papers:

| Method area | Paper ID | Shortlist metadata |
|---|---|---|
| KGACG structured intent | `2510.19868` | `runs/f6e76e79b15c/screen/shortlist.json` |
| MIDS-Valve structured intent | `2510.01736` | `runs/f6e76e79b15c/screen/shortlist.json` |
| JML-Autodoc executable contracts | `2506.09230` | `runs/f6e76e79b15c/screen/shortlist.json` |
| PVBench vulnerability benchmark | `2603.06858` | `runs/6ad47d8c033f/screen/shortlist.json` |
| RIG / repository graph impact | `2601.10112` | `runs/d25bdf3ef65d/screen/shortlist.json` |
| Evo-Memory trajectory memory | `2511.20857` | `runs/86337a1a0637/screen/shortlist.json` |
| Agent-HER experience replay | `2603.21357` | `runs/86337a1a0637/screen/shortlist.json` |
| SWD-Bench benchmark evidence | `2604.06793` | `runs/84cdd6da8be8/screen/shortlist.json` |
| Repo-path retrieval / repository QA | `2510.08850` | `runs/84cdd6da8be8/screen/shortlist.json` |
| CodeCureAgent vulnerability repair | `2509.11787` | `runs/30b9f729ff75/screen/shortlist.json` |

The `research-pipeline` CLI is installed locally. For the missing target papers,
the next pass should resume the corresponding run IDs and execute the normal
download/convert stages, subject to the repository's network/data policy. For
the three available converted papers, the next pass can review the Markdown
directly and add paper-backed evidence rows without touching raw PDFs.
