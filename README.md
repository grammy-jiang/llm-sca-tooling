# llm-sca-tooling

**Evidence-first, LLM-augmented static code analysis.**

`llm-sca-tooling` gathers *typed evidence* from your repository — AST symbols,
call graphs, SARIF alerts, tests, runtime traces — grades it
(`parser > analyser > heuristic > unknown`), and only then lets an LLM reason
over the graded context. Findings carry their evidence grade; the tool never
upgrades confidence on its own, and it never edits your source. Humans decide
on remediation.

## Five product surfaces

1. **MCP server** — the primary integration surface: 45+ tools, 14 resources,
   12 prompts over stdio or Streamable HTTP. Point Claude Code (or any MCP
   client) at it and ask questions about your repository with
   evidence-graded answers.
2. **Workflow orchestrator** — bug resolve, patch review, SAST alert repair,
   implementation check (spec-vs-code compliance), and fault localisation.
   Every run produces a structured report, a run record, and a harness
   condition sheet.
3. **Evaluation harness** — a T1–T4 benchmark ladder with calibration
   reports; T1 runs in null mode (no LLM) and gates every CI check.
4. **Operational harness plane** — run records, incident tracking, trajectory
   memory with experience replay, operational reviews, release gates.
5. **Operational guardrails** — permission profiles, doom-loop and budget
   monitoring, governance-drift checks, privacy redaction, session replay.

## Install

```bash
pipx install llm-sca-tooling          # CLI + MCP server
# optional capabilities:
pipx inject llm-sca-tooling fastembed # semantic retrieval (embeddings)
pipx inject llm-sca-tooling anthropic # live LLM boundaries (llm_mode)
```

or in a project:

```bash
pip install "llm-sca-tooling[embeddings,llm]"
```

Graph indexing uses `universal-ctags` (`apt install universal-ctags` /
`brew install universal-ctags`).

### Optional: full-fidelity TypeScript/JavaScript

The TypeScript/JavaScript backend uses **ts-morph** for parser-grade facts
(resolved cross-file imports and call edges). It needs Node.js and a one-time
dependency install:

```bash
cd <site-packages>/llm_sca_tooling/indexing/backends/typescript/runner
npm install
```

Without Node/ts-morph the backend transparently falls back to a heuristic
regex parser — lower fidelity, but indexing still works.

### Optional: full-fidelity C/C++

The C/C++ backend uses **libclang** (`clang.cindex`) for parser-grade facts
(resolved symbols, `#include` edges, cross-file call edges). The `cpp` extra
bundles a loadable libclang — no system toolchain needed:

```bash
pip install "llm-sca-tooling[cpp]"
```

It honours `compile_commands.json` at the repo root when present. Without
libclang the backend falls back to the heuristic regex parser.

## Quickstart

```bash
llm-sca-tooling config validate
llm-sca-tooling mcp serve --transport stdio   # start the MCP server
```

Register with Claude Code:

```bash
claude mcp add llm-sca-tooling -- llm-sca-tooling mcp serve
```

Then, from your MCP client:

```text
register_repo(repo_path="/path/to/repo")
graph_build(repo_path="/path/to/repo")        # async — poll task_status
get_relevant_files(issue_text="NullPointerException in UserService.authenticate")
run_implementation_check(spec="<your architecture doc>", task=true)
run_issue_resolution(issue_text="<bug report>")
```

### LLM mode

Workflows run in **null mode** by default — deterministic heuristics only,
suitable for CI. With the `llm` extra installed and `ANTHROPIC_API_KEY`
exported, pass `llm_mode: true` to `run_implementation_check` to enable the
LLM boundaries (clause grounding, contract generation). Runs degrade to null
mode when no provider is available and report `llm_mode_active` so a degraded
run is never mistaken for an LLM-graded one. Model selection via
`LLM_SCA_MODEL` (default `claude-opus-4-8`).

## Evidence hierarchy

| Grade | Source | Confidence |
|---|---|---|
| `parser` | ctags AST, language servers, exact SARIF locations | High |
| `analyser` | dataflow, cross-file call graph | Medium-high |
| `heuristic` | pattern matching, keyword search, LLM-classified groundings | Medium |
| `unknown` | no hard evidence — reported honestly, never auto-passed | Low |

Every LLM-derived artefact is fail-closed: unparseable output degrades to the
deterministic null path, citations are filtered to evidence actually
provided, generated predicates must compile before they count, and LLM
groundings carry a `derivation="llm"` audit field.

## Governance

Development of this repository is governed by [AGENTS.md](AGENTS.md): hard
constraints (no secrets, write allowlists, deny-by-default egress), a
verify-before-commit gate (`make verify`), live session telemetry, and
harness condition sheets for every evaluation and release run.

## Documentation

- [Installation](docs/installation.md) ·
  [Quickstart](docs/quickstart.md) ·
  [Architecture](docs/architecture.md)
- [Evaluation guide](docs/evaluation-guide.md) ·
  [Harness setup](docs/harness-setup-guide.md) ·
  [Plugin authoring](docs/plugin-authoring-guide.md) ·
  [Incident response](docs/incident-response-guide.md)
- [CHANGELOG](CHANGELOG.md)

## License

[MIT](LICENSE)
