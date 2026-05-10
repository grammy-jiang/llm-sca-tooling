# MCP server core

Phase 4 exposes indexed repository evidence through the local
`code-intelligence` server facade.

```python
from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig

server = CodeIntelligenceServer(McpServerConfig.for_workspace(".llm-sca")).start()
resources = server.list_resources()
tools = server.list_tools()
```

The development CLI uses JSON-lines over stdin/stdout:

```bash
evidence-sca mcp serve --workspace .llm-sca
```

## Setup Modes

`evidence-sca setup` configures all supported local agent clients:

- Claude Code: `.mcp.json`
- GitHub Copilot: `.vscode/mcp.json`
- OpenAI Codex CLI: `.codex/config.toml`

There are two expected deployment cases:

1. **Developing this repository.** Run setup from the `evidence-sca` checkout.
   The command auto-detects the source checkout and writes MCP entries that use
   `uv run evidence-sca mcp serve`, so the clients talk to the local editable
   implementation and the `.llm-sca` workspace under this repository.
2. **Using the installed package in another project.** Run setup from the target
   project directory after installing the package. The command writes MCP
   entries that use the installed `evidence-sca mcp serve` binary and installs
   product workflow skill templates into that project's `.skills/` directory
   without overwriting existing files.

In both cases the MCP server exposes the same skill surface through
`code-intelligence://skills` and `code-intelligence://skills/{name}`. If a target
project does not have local skill files yet, the server falls back to bundled
package templates, so installed-package mode is not dependent on this source
checkout.

Implemented resources include repository registry, repository-local skill
templates, Phase 1 schema exports, graph manifests, graph slices, cached
summaries, cached blame-chain artefacts, build/test evidence, SARIF evidence,
evaluation runs, trajectory memory, and operational records. The skill-template
resources are:

- `code-intelligence://skills` — inventory of product workflow templates from
  `.skills/` and harness templates from `.agent/skills/`.
- `code-intelligence://skills/{name}` — full template content for a named
  skill, preferring the richer product template when both locations define the
  same skill.

Implemented tools include repo registration, task-capable graph build/update,
graph slicing, caller/callee queries, cached blame lookup, repo-QA,
fault-localisation, patch review, issue resolution, implementation check,
SAST repair, evaluation, memory, and operational harness tools.

Prompt retrieval returns structured workflow instructions only; it does not
execute audit, repair, review, or readiness workflows. Long-running execution is
started through the corresponding task-capable MCP tools.
