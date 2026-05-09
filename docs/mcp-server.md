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

Implemented resources include repository registry, Phase 1 schema exports, graph
manifests, graph slices, cached summaries, cached blame-chain artefacts, and
build/test evidence. Implemented tools include repo registration, task-capable
graph build/update, graph slicing, caller/callee queries, cached blame lookup,
and the Phase 7 `plugin_reload` placeholder.

Prompt retrieval returns structured stubs only; it does not execute audit,
repair, review, or readiness workflows in Phase 4.
