# Plugin Authoring Guide

> This guide covers writing a Phase 7 cross-language interface plugin for `evidence-sca`.
> Plugins extend the tool to languages that `universal-ctags` does not support, or to
> frameworks that require framework-specific interface analysis (e.g., gRPC, GraphQL, OpenAPI).

---

## Limitations

- Plugins produce `analyser`-grade evidence at best. `parser`-grade evidence requires
  a language server or an AST-level parser, which plugins do not provide.
- Plugin performance is bounded by hub dampening: symbols with >100 callers are treated
  as hub nodes and do not propagate evidence to all callers.
- The plugin system does not support mutating the graph; plugins only index and link.
- A plugin that raises an exception during `detect` or `index` is logged and skipped;
  it does not halt the graph build.
- Quality claims for plugin-generated findings must reference calibration results from
  the Phase 10 evaluation harness, not from ad hoc testing.
- A `HarnessConditionSheet` must be completed for any evaluation run that uses a plugin.

---

## The Four-Method Contract

Every plugin must implement `InterfacePluginBase`:

```python
from llm_sca_tooling.plugins.interface_plugin_base import InterfacePluginBase
from llm_sca_tooling.schemas.interface import InterfaceRecord, InterfaceOperation

class MyPlugin(InterfacePluginBase):
    def detect(self, repo_path: str) -> bool:
        """Return True if this plugin applies to the repository."""
        ...

    def index(self, repo_path: str) -> list[InterfaceRecord]:
        """Return all interface records discovered in the repository."""
        ...

    def link(
        self, record: InterfaceRecord, graph_nodes: list[dict]
    ) -> list[tuple[str, str]]:
        """Return (source_node_id, target_node_id) edges to add to the graph."""
        ...

    def traverse(
        self, record: InterfaceRecord, direction: str
    ) -> list[InterfaceOperation]:
        """Return operations reachable from record in the given direction."""
        ...
```

### Method responsibilities

| Method | Responsibility | Must return |
|---|---|---|
| `detect` | Determine applicability. Called once per graph build. | `bool` |
| `index` | Discover all interface records. May be slow; runs in executor. | `list[InterfaceRecord]` |
| `link` | Produce graph edges for a record. Called per record. | `list[tuple[str, str]]` |
| `traverse` | List reachable operations. Called per record at query time. | `list[InterfaceOperation]` |

---

## Key Schemas

### `InterfaceRecord`

```python
class InterfaceRecord(BaseModel):
    interface_id: str          # unique, stable across graph builds
    plugin_id: str             # your plugin's ID
    interface_type: str        # e.g., "grpc", "graphql", "rest", "thrift"
    source_file: str           # relative path within repo
    line_number: int | None
    name: str                  # interface/service name
    confidence: str            # "parser" | "analyser" | "heuristic"
    metadata: dict[str, Any]   # plugin-specific extra data
```

### `InterfaceOperation`

```python
class InterfaceOperation(BaseModel):
    operation_id: str
    interface_id: str
    name: str                  # method/field/endpoint name
    direction: str             # "inbound" | "outbound" | "bidirectional"
    signature: str | None
    confidence: str
```

### `GeneratedArtifactRecord`

If your plugin generates files (e.g., from a proto schema), record them:

```python
from llm_sca_tooling.schemas.interface import GeneratedArtifactRecord

artifact = GeneratedArtifactRecord(
    artifact_id="...",
    plugin_id="my-plugin",
    source_interface_id="...",
    generated_file="path/to/generated.py",
    generator_version="1.0.0",
)
```

---

## Testing a Plugin with the Null Corpus Adapter

Use the null corpus adapter to test your plugin without a real repository:

```python
from llm_sca_tooling.plugins.null_corpus_adapter import NullCorpusAdapter
from my_package.my_plugin import MyPlugin

adapter = NullCorpusAdapter(
    files={
        "service.proto": 'syntax = "proto3"; service Greeter { rpc Hello (Req) returns (Res); }',
        "server.py": "# stub",
    }
)
plugin = MyPlugin()

assert plugin.detect(adapter.repo_path)
records = plugin.index(adapter.repo_path)
assert len(records) > 0
assert records[0].confidence in ("parser", "analyser", "heuristic")

edges = plugin.link(records[0], graph_nodes=[])
ops = plugin.traverse(records[0], direction="inbound")
```

Run tests with:
```bash
uv run pytest tests/ -k "my_plugin" -x
```

---

## Registering a Plugin

### At runtime (via MCP tool)

```
plugin_reload(plugin_id="my_plugin", repo_path="/path/to/repo")
```

### At startup (via configuration)

Add to your `evidence-sca` config:

```toml
[plugins]
enabled = ["my_package.my_plugin:MyPlugin"]
```

---

## Performance Considerations

### Hub dampening

Nodes with more than 100 callers are treated as hub nodes. Edges to/from hub nodes
are present in the graph but **do not propagate evidence** to all callers. This
prevents a single widely-imported utility from inflating blast radius scores.

Set a custom hub threshold per plugin:

```python
class MyPlugin(InterfacePluginBase):
    hub_threshold: int = 50  # lower threshold for dense service meshes
```

### Confidence levels

- Use `parser` only if you parse an AST or schema definition file with a proper parser.
- Use `analyser` for pattern-matched structural analysis (regex on well-defined formats).
- Use `heuristic` for keyword-based detection or best-effort analysis.

### Async index

If your `index` method performs IO (file reads, subprocess calls), it runs in
`loop.run_in_executor` automatically. Keep it CPU-bound where possible.

---

## Example: Minimal gRPC Plugin

```python
import re
from pathlib import Path

from llm_sca_tooling.plugins.interface_plugin_base import InterfacePluginBase
from llm_sca_tooling.schemas.interface import InterfaceRecord, InterfaceOperation


class GRPCPlugin(InterfacePluginBase):
    plugin_id = "grpc"

    def detect(self, repo_path: str) -> bool:
        return any(Path(repo_path).rglob("*.proto"))

    def index(self, repo_path: str) -> list[InterfaceRecord]:
        records = []
        for proto_file in Path(repo_path).rglob("*.proto"):
            content = proto_file.read_text()
            for match in re.finditer(r"service\s+(\w+)", content):
                records.append(
                    InterfaceRecord(
                        interface_id=f"grpc:{proto_file.relative_to(repo_path)}:{match.group(1)}",
                        plugin_id=self.plugin_id,
                        interface_type="grpc",
                        source_file=str(proto_file.relative_to(repo_path)),
                        line_number=content[: match.start()].count("\n") + 1,
                        name=match.group(1),
                        confidence="analyser",
                        metadata={},
                    )
                )
        return records

    def link(self, record: InterfaceRecord, graph_nodes: list[dict]) -> list[tuple[str, str]]:
        return []  # simplified: no graph edges in this minimal example

    def traverse(self, record: InterfaceRecord, direction: str) -> list[InterfaceOperation]:
        return []  # simplified
```

---

## Related Documents

- [Architecture Overview](architecture.md) — evidence hierarchy and product surfaces.
- [Evaluation Guide](evaluation-guide.md) — validate plugin quality with the eval harness.
- [Quickstart Guide](quickstart.md) — register and run against a real repository.
