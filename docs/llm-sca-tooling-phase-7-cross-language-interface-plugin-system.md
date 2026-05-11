# LLM-SCA Tooling Phase 7 Implementation Plan: Cross-Language Interface Plugin System

> Date: 2026-05-09  
> Repository name: `evidence-sca`  
> Source plan: `llm-sca-tooling-implementation-plan.md`  
> Source architecture: `llm-sca-tooling-architecture.md`  
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 7 - Cross-Language Interface Plugin System  
> Primary objective: implement the extensible cross-language interface plugin system with a four-method plugin contract (`detect`, `index`, `link`, `traverse`), the `InterfaceRecord` model, a plugin registry, a cross-language traversal engine, and three built-in plugin MVPs (HTTP-REST, WebSocket, omniORB-IDL), then expose the results through the `trace_cross_language` MCP tool, the `plugin_reload` MCP tool (graduating from its Phase 4 stub), and the `code-intelligence://interfaces` resource family.

---

## 1. Phase Summary

Phases 3–6 built deterministic evidence within each language. Phase 7 connects those language graphs across boundaries. The cross-language interface plugin system is the mechanism that makes `find_callers`, `find_callees`, and `trace_cross_language` follow call chains through HTTP routes, WebSocket events, and IDL method calls — automatically, as part of every graph traversal — without the core server encoding any knowledge of specific interface types.

The central rule for this phase is:

```text
Cross-language links are evidence, not assertions.
Every interface link must carry a confidence level, a binding type,
and a plugin-sourced provenance record.
Ambiguous interface matches are exposed as low-confidence candidates.
They are never silently promoted to confirmed impact.
```

Phase 7 should implement:

- Plugin base interface with `detect`, `index`, `link`, and `traverse` methods.
- `InterfaceRecord` and `InterfaceOperation` models.
- Plugin capability registry.
- Cross-language traversal engine that chains hops across all registered plugins.
- HTTP-REST plugin MVP: OpenAPI/Swagger parsing, framework route detection (FastAPI, Flask, Django), JS/TS client detection, URL normalization, request/response schema extraction.
- WebSocket plugin MVP: socket.io server/client event detection, event-name and payload-shape extraction, namespace resolution.
- omniORB-IDL plugin MVP: `omniidl` AST output, C++ POA skeleton and servant linker, Python stub linker, Python caller detection via pyan3.
- Plugin backlog registration point for gRPC, Protobuf, ZeroMQ, MQTT, and DBUS.
- `trace_cross_language` MCP tool.
- `plugin_reload` MCP tool graduating from its Phase 4 no-op stub.
- `code-intelligence://interfaces` and `code-intelligence://interfaces/{plugin_id}/{interface_name}` MCP resources.
- Traversal integration into existing `find_callers`, `find_callees`, and `get_graph_slice` tools.
- Graph node and edge population for `idl_interface`, `http_route`, `websocket_event`, `implements`, `exposes`, `consumes`, and `ffi` types.

### Architecture Coverage

Phase 7 covers:

- Interface plugin contract.
- F8 foundation: cross-language and cross-repo graph facts produced by plugins.
- `code-intelligence://interfaces` resource.
- `code-intelligence://interfaces/{plugin_id}/{interface_name}` resource.
- `trace_cross_language` MCP tool.
- `plugin_reload` MCP tool (from Phase 4 stub to working implementation).
- Graph node types: `idl_interface`, `http_route`, `websocket_event`.
- Graph edge types: `implements`, `exposes`, `consumes`, `ffi`.

### Inherited Paper Anchors

Use these anchors in Phase 7 issues, ADRs, plugin design notes, and traversal reports:

- `rig`
- `logiclens`
- `eagle-x`
- `mids-valve`
- `jml-autodoc`
- `swe-polybench`
- `defects4c`

Adjacent anchors useful for specific plugin notes:

- `arise`
- `cosil`
- `predicatefix`
- `nullrepair`

## Technology Stack

| Library / Tool | PyPI package | Version | Purpose in this phase |
|---|---|---|---|
| httpx | `httpx` | >=0.27 | Async HTTP client for the HTTP-REST plugin; wrapped in `PolicyAwareHTTPClient` to enforce HC5 network policy; all fetch calls are `async def` |
| lxml.html | `lxml` | >=5.2 | Structural HTML parsing of OpenAPI documentation pages and framework-generated HTML; XPath and CSS selector traversal |
| selectolax | `selectolax` | >=0.3 | High-throughput HTML5 parsing (Lexbor engine, 5–30x faster than BeautifulSoup) for bulk route-documentation pages where performance matters |
| orjson | `orjson` | >=3.10 | Parsing OpenAPI/Swagger JSON documents; primary JSON I/O throughout the plugin system |
| ruamel.yaml | `ruamel.yaml` | >=0.18 | Parsing OpenAPI/Swagger YAML documents; YAML 1.2 compliant; safe mode required for untrusted input |
| Pydantic v2 | `pydantic` | >=2.0 (`extra="forbid"`) | `InterfaceRecord`, `InterfaceOperation`, plugin capability models; `model_json_schema()` for schema export |
| Semgrep | `semgrep` | latest available | Route and event pattern detection rules for HTTP-REST and WebSocket plugins; invoked via `asyncio.create_subprocess_exec`; never `subprocess.run` in async paths |

Notes:

- FastAPI, Flask, Django, Express, and socket.io are **target frameworks being detected**, not project dependencies. The plugin system analyses arbitrary user codebases; it does not import these frameworks.
- `httpx` calls in the HTTP-REST plugin must go through `PolicyAwareHTTPClient` to satisfy HC5. Direct `httpx.get` or `httpx.AsyncClient` usage without the policy wrapper is not permitted.
- `ruamel.yaml` safe mode (`YAML(typ="safe")`) is required when parsing OpenAPI/Swagger YAML sourced from user repositories (untrusted input).

---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 7 depends on:

- Phase 1 schemas:
  - Graph node types: `idl_interface`, `http_route`, `websocket_event`, `grpc_service`, `protobuf_message`, `file`, `class`, `function`, `method`.
  - Graph edge types: `implements`, `exposes`, `consumes`, `ffi`, `calls`, `imports`, `dataflow`.
  - `InterfaceRecord` fields in the architecture: `interface_id`, `kind`, `generated_artifacts`.
  - Provenance model with `repo_id`, `git_sha`, `snapshot_id`, `file`, `span`, `confidence`, `derivation`.
  - Confidence and derivation enums.
- Phase 2 stores:
  - Repository registry (for cross-repo link target resolution).
  - Graph store (add-node, add-edge, fetch by type, fetch by file/span, fetch by ID).
  - Artefact registry.
  - Snapshot ledger.
- Phase 3/5 language backends:
  - Python AST-indexed function/method nodes for route handler and stub-caller discovery.
  - pyan3 call-graph edges for Python caller tracing.
  - TypeScript ts-morph symbol and import nodes for client-side detection.
  - C/C++ libclang symbol nodes for servant class detection.
  - Build evidence nodes for framework detection hints.
- Phase 4 MCP:
  - `plugin_reload` tool stub to graduate.
  - Task manager for long-running plugin index passes.
  - Notification infrastructure for `interfaces` resource updates and list-changed.
  - Tool registry and permission descriptor model.
- Phase 5 backends:
  - Python import resolver for stub module detection.
  - LSP abstraction layer (reusable for any future LSP-based plugin).
- Phase 6 SARIF:
  - Semgrep-based route and WebSocket event detection rules (optional augmentation path for plugin detection).

### Phase Outputs

Phase 7 should produce:

- Plugin base interface and abstract classes.
- `InterfaceRecord` and `InterfaceOperation` models.
- Plugin capability registry.
- Plugin capability descriptor model.
- Cross-language traversal engine.
- HTTP-REST plugin with OpenAPI parser and framework/client detectors.
- WebSocket plugin with server and client detectors.
- omniORB-IDL plugin with IDL parser, servant linker, stub linker, and caller finder.
- Plugin backlog registration stubs (gRPC, Protobuf, ZeroMQ, MQTT, DBUS).
- `trace_cross_language` MCP tool.
- `plugin_reload` MCP tool (working implementation replacing Phase 4 stub).
- `code-intelligence://interfaces` and `code-intelligence://interfaces/{plugin_id}/{interface_name}` resource handlers.
- Traversal integration in `find_callers` and `find_callees`.
- Interface graph nodes and edges populated in Phase 2 graph store.
- URL normalization utility.
- Fixture repositories for HTTP-REST, WebSocket, and omniORB-IDL integration tests.

### Non-Goals

Do not implement these in Phase 7:

- Fault localisation ranking. That is Phase 9.
- Blast-radius computation. That is Phase 15.
- Bug-resolve workflow. That is Phase 13.
- Patch-review interface compatibility check. That is Phase 11.
- gRPC, Protobuf, ZeroMQ, MQTT, and DBUS full implementations. Those are future plugins.
- LLM-based route/event name inference for dynamic cases. Ambiguous dynamic cases stay as low-confidence candidates.
- Runtime network traffic capture for interface discovery. Phase 7 is static detection only.
- OpenAPI schema generation from unannotated code.

---

## 3. Recommended File Layout

```text
src/evidence_sca/
  plugins/
    __init__.py
    base.py
    registry.py
    capability.py
    interface_record.py
    traversal.py
    errors.py

  plugins/http_rest/
    __init__.py
    plugin.py
    openapi_parser.py
    fastapi_detector.py
    flask_detector.py
    django_detector.py
    client_detector.py
    url_normalizer.py
    schema_extractor.py

  plugins/websocket/
    __init__.py
    plugin.py
    server_detector.py
    client_detector.py
    event_extractor.py
    namespace_resolver.py

  plugins/omniorb_idl/
    __init__.py
    plugin.py
    idl_parser.py
    cpp_servant_linker.py
    python_stub_linker.py
    caller_finder.py
    generated_artifact_tracker.py

  plugins/backlog/
    __init__.py
    grpc_stub.py
    protobuf_stub.py
    zeromq_stub.py
    mqtt_stub.py
    dbus_stub.py

  mcp_server/tools/
    interface.py

  mcp_server/resources/
    interfaces.py

tests/
  plugins/
    fixtures/
      http_rest/
        fastapi_server.py
        flask_server.py
        django_server/
          urls.py
          views.py
        ts_client/
          client.ts
          tsconfig.json
        openapi.yaml
        swagger_v2.json
      websocket/
        socketio_server.py
        socketio_client.ts
        tsconfig.json
      omniorb_idl/
        calculator.idl
        calculator_skel.cc
        calculatorSK.cc
        calculator_servant.cc
        calculator_idl.py
        calculator_client.py
      mixed_interface/
        python_server.py
        ts_client.ts
        calculator.idl
    test_plugin_base.py
    test_plugin_registry.py
    test_interface_record.py
    test_capability.py
    test_traversal.py
    http_rest/
      test_openapi_parser.py
      test_fastapi_detector.py
      test_flask_detector.py
      test_django_detector.py
      test_client_detector.py
      test_url_normalizer.py
      test_schema_extractor.py
      test_http_rest_plugin.py
    websocket/
      test_server_detector.py
      test_client_detector.py
      test_event_extractor.py
      test_namespace_resolver.py
      test_websocket_plugin.py
    omniorb_idl/
      test_idl_parser.py
      test_cpp_servant_linker.py
      test_python_stub_linker.py
      test_caller_finder.py
      test_generated_artifact_tracker.py
      test_omniorb_idl_plugin.py
    backlog/
      test_backlog_stubs.py
    test_trace_cross_language.py
    test_plugin_reload.py
    test_interface_resources.py
    test_traversal_integration.py
    test_find_callers_cross_language.py
    test_integration.py
```

---

## 4. Interface Plugin Architecture

### 4.1 Design Principle

The core server has no hard-coded knowledge of any specific interface type. All such knowledge lives in plugins. A plugin is a self-contained Python class that:

- Identifies interface definition files in a repository (`detect`).
- Parses those files and extracts interface contracts (`index`).
- Links abstract interface operations to concrete code nodes in the language graph (`link`).
- Given a concrete code node, returns the set of reachable nodes on the other side of the interface boundary (`traverse`).

This design means adding a new interface type — such as gRPC — requires only writing a plugin class, not modifying any existing graph, traversal, or MCP code.

### 4.2 Interface Types In The Graph Schema

Phase 1 defined these interface boundary node types:

- `idl_interface` — an omniORB IDL interface (or any IDL-style interface).
- `http_route` — an HTTP/REST endpoint or route handler.
- `websocket_event` — a WebSocket event, channel, or subscription.
- `grpc_service` — a gRPC service (reserved for future gRPC plugin).
- `protobuf_message` — a Protobuf message type (reserved for future plugin).

And these edge types for interface traversal:

- `implements` — a concrete code class or function implements an abstract interface node.
- `exposes` — a server-side handler or servant exposes an interface operation.
- `consumes` — a client-side callsite consumes an interface operation.
- `ffi` — a foreign-function or cross-language boundary (used by omniORB-IDL for the C++/Python boundary).

### 4.3 Plugin Run-Time Contract

Plugins run in two modes:

**Index-time mode** (called by `graph_build`, `graph_update`, and `plugin_reload`):
- `detect` scans the repository for interface definition files.
- `index` parses those files and builds `InterfaceRecord` objects.
- `link` emits graph nodes and edges to the Phase 2 graph store.

**Query-time mode** (called by `traverse_cross_language` and related tools):
- `traverse` performs a graph lookup for boundary-crossing edges from a given node. This is a graph read, not a parse.

Index-time operations are expensive and cached. Query-time operations are fast graph lookups on pre-indexed data.

### 4.4 Plugin Isolation Rules

- Plugins must not import from other plugins.
- Plugins may use Phase 5 language backend utilities (AST indexer, pyan3 adapter, ts-morph adapter, libclang adapter) through stable interfaces.
- Plugins must not run LLM calls. Ambiguous matches are recorded as low-confidence candidates.
- Plugin-emitted nodes and edges must validate against Phase 1 schemas.
- Plugin-emitted graph facts must carry `plugin_id` and `plugin_version` in provenance.

---

## 5. Plugin Base Interface

### 5.1 `InterfacePluginBase`

Recommended abstract base class:

```text
InterfacePluginBase
  plugin_id : str
  plugin_version : str
  interface_kind : InterfaceKind

  check_availability() -> PluginAvailability
    # Check required external tools and libraries.
    # Fast, side-effect-free.

  describe_capability() -> PluginCapabilityDescriptor
    # Return interface kinds, graph node/edge types, and confidence levels.

  detect(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    file_list: list[RepoRelativePath],
  ) -> PluginDetectResult
    # Identify files that constitute interface definitions for this plugin.
    # Must not parse or link. Fast heuristic scan only.

  index(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    detect_result: PluginDetectResult,
    config: PluginConfig,
  ) -> PluginIndexResult
    # Parse the detected interface definitions.
    # Extract InterfaceRecord objects.
    # Must not write to the graph store.

  link(
    repo: RepositoryRecord,
    snapshot: SnapshotDescriptor,
    index_result: PluginIndexResult,
    graph_store: GraphStoreQuery,
    config: PluginConfig,
  ) -> PluginLinkResult
    # Connect InterfaceRecord operations to existing graph nodes.
    # Emit graph nodes (http_route, idl_interface, websocket_event, ...).
    # Emit graph edges (implements, exposes, consumes, ffi).
    # Write to the graph store.

  traverse(
    node_id: str,
    direction: TraversalDirection,
    graph_store: GraphStoreQuery,
  ) -> list[TraversalLink]
    # Query pre-indexed graph edges for cross-boundary links from node_id.
    # Pure graph read. Must not re-parse source files.
```

### 5.2 `PluginDetectResult`

```text
PluginDetectResult
  plugin_id : str
  repo_id : str
  snapshot_id : str
  detected_files : list[DetectedInterfaceFile]
  detection_confidence : ConfidenceLevel
  diagnostics : list[IndexDiagnostic]
  run_stats : BackendRunStats

DetectedInterfaceFile
  file_path : RepoRelativePath
  interface_type_hint : str
  detection_method : str   # extension, pattern_match, openapi_header, etc.
  confidence : ConfidenceLevel
```

### 5.3 `PluginIndexResult`

```text
PluginIndexResult
  plugin_id : str
  repo_id : str
  snapshot_id : str
  interface_records : list[InterfaceRecord]
  generated_artifact_refs : list[ArtifactRef]
  diagnostics : list[IndexDiagnostic]
  run_stats : BackendRunStats
```

### 5.4 `PluginLinkResult`

```text
PluginLinkResult
  plugin_id : str
  repo_id : str
  snapshot_id : str
  nodes_emitted : int
  edges_emitted : int
  interface_records_linked : int
  ambiguous_links : list[AmbiguousLinkRecord]
  diagnostics : list[IndexDiagnostic]
  run_stats : BackendRunStats

AmbiguousLinkRecord
  interface_id : str
  operation_name : str
  candidate_node_ids : list[str]
  reason : str
```

### 5.5 `TraversalLink`

```text
TraversalLink
  from_node_id : str
  to_node_id : str
  via_interface_id : str
  plugin_id : str
  edge_type : str          # implements, exposes, consumes, ffi
  confidence : ConfidenceLevel
  operation_name : str | None
  direction : TraversalDirection  # outbound, inbound
```

### 5.6 Availability Check

`PluginAvailability`:

```text
PluginAvailability
  plugin_id : str
  available : bool
  missing_deps : list[str]
  tool_paths : dict[str, str]
  warnings : list[str]
```

---

## 6. InterfaceRecord And Operation Model

### 6.1 `InterfaceRecord`

`InterfaceRecord` is the central output of every plugin's `index` phase. One record represents one named interface boundary (e.g., one HTTP path prefix, one IDL interface, one WebSocket namespace).

```text
InterfaceRecord
  interface_id : str              # Stable ID: hash of (plugin_id, kind, interface_name, repo_id)
  kind : InterfaceKind            # http, websocket, idl, grpc, protobuf, ...
  plugin_id : str
  plugin_version : str
  interface_name : str            # Human-readable: "GET /users/{id}", "Calculator", "chat:message"
  version : str | None
  definition_files : list[RepoRelativePath]
  source_repos : list[str]        # Repos whose files define or implement this interface
  operations : list[InterfaceOperation]
  generated_artifacts : list[GeneratedArtifactRecord]
  confidence : ConfidenceLevel    # exact, inferred, or ambiguous
  snapshot_ids : dict[str, str]   # repo_id -> snapshot_id at index time
  provenance : ProvenanceRecord
```

### 6.2 `InterfaceKind` Enum

```text
InterfaceKind
  http       # HTTP/REST routes
  websocket  # WebSocket events and channels
  idl        # omniORB IDL (and other IDL-style interfaces)
  grpc       # gRPC (future)
  protobuf   # Protobuf message types (future)
  zeromq     # ZeroMQ sockets (future)
  mqtt       # MQTT topics (future)
  dbus       # D-Bus interfaces (future)
  custom     # Plugin-defined extension kind
```

### 6.3 `InterfaceOperation`

One operation represents one callable endpoint, method, event, or RPC within an interface.

```text
InterfaceOperation
  operation_id : str              # hash of (interface_id, operation_name, method)
  interface_id : str
  name : str                      # Route path, method name, event name, RPC name
  operation_type : OperationType  # route, method, event, rpc
  http_method : str | None        # GET, POST, PUT, DELETE, PATCH, WS
  path_pattern : str | None       # Canonical normalized URL pattern
  input_schema : dict | None      # JSON Schema or equivalent
  output_schema : dict | None
  parameters : list[OperationParameter]
  status_codes : list[int] | None
  auth_hints : list[str] | None   # oauth2, api_key, bearer, none
  server_handler_node_ids : list[str]   # Phase 5 graph nodes for handlers/servants
  client_callsite_node_ids : list[str]  # Phase 5 graph nodes for client callsites
  confidence : ConfidenceLevel
  binding_method : str            # openapi, ast_decorator, semgrep, idl_ast, ...
```

### 6.4 `OperationParameter`

```text
OperationParameter
  name : str
  location : str        # path, query, header, body, cookie
  schema : dict | None
  required : bool
  nullable : bool
```

### 6.5 `GeneratedArtifactRecord`

Tracks files that were generated from an interface definition and must not be edited directly.

```text
GeneratedArtifactRecord
  artifact_id : str
  source_interface_id : str
  generator_tool : str            # omniidl, grpc, protoc, openapi-generator, ...
  file_paths : list[RepoRelativePath]
  is_checked_in : bool
  regeneration_command : str | None
  provenance : ProvenanceRecord
```

Rules:

- Generated artifacts must be marked in the graph as `generated=True` on their `file` nodes.
- Blast-radius (Phase 15) and patch-review (Phase 11) must not recommend manual edits to generated files.
- If a generated file is modified, emit a warning that the source interface definition should be changed instead.

---

## 7. Plugin Registry And Capability Model

### 7.1 `PluginRegistry`

```text
PluginRegistry
  register(plugin: InterfacePluginBase) -> None
    # Add plugin. Fail on duplicate plugin_id.

  unregister(plugin_id: str) -> None

  get(plugin_id: str) -> InterfacePluginBase | None

  available_plugins() -> list[InterfacePluginBase]
    # Return only plugins that pass availability check.

  all_plugins() -> list[InterfacePluginBase]
    # Return all registered plugins regardless of availability.

  capability_report() -> list[PluginCapabilityDescriptor]

  availability_report() -> list[PluginAvailability]
```

### 7.2 `PluginCapabilityDescriptor`

```text
PluginCapabilityDescriptor
  plugin_id : str
  plugin_version : str
  interface_kinds : list[InterfaceKind]
  supported_server_languages : list[str]
  supported_client_languages : list[str]
  emitted_node_types : list[GraphNodeType]
  emitted_edge_types : list[GraphEdgeType]
  max_confidence : ConfidenceLevel
  requires_external_tools : list[str]
  requires_build_artifacts : bool
  incremental_support : bool
```

### 7.3 Plugin State In Operational Store

Each plugin index pass is recorded as a run event including:

- Plugin ID and version.
- Repos indexed.
- Snapshot IDs per repo.
- Interface records produced.
- Nodes and edges emitted.
- Ambiguous links count.
- Diagnostics summary.
- Wall time.

### 7.4 Registry Tests

Required tests:

- Register plugin.
- Duplicate registration fails.
- Availability check returns correct subset.
- Capability report includes all registered plugins.
- Unregister removes plugin and its capability from report.
- Capability descriptor snapshot is stable.

---

## 8. Cross-Language Traversal Engine

### 8.1 Purpose

`traversal.py` implements the `trace_cross_language` core logic. It chains hops across all registered plugins in sequence, following `implements`, `exposes`, `consumes`, and `ffi` edges through the graph until no more cross-language links exist or a bound is reached.

### 8.2 `CrossLanguageTraverser`

```text
CrossLanguageTraverser
  plugin_registry : PluginRegistry
  graph_store : GraphStoreQuery

  traverse(
    start_node_id: str,
    direction: TraversalDirection,  # outbound, inbound, both
    max_hops: int,
    plugins: list[str] | None,      # None = all available plugins
    min_confidence: ConfidenceLevel | None,
  ) -> CrossLanguageTraversalResult
```

### 8.3 `CrossLanguageTraversalResult`

```text
CrossLanguageTraversalResult
  start_node_id : str
  hops : list[TraversalHop]
  total_hops : int
  reached_node_ids : list[str]
  terminated_early : bool
  termination_reason : str | None  # max_hops, no_more_links, confidence_cutoff
  ambiguous_candidates : list[AmbiguousCandidate]
  cross_repo_hops : list[CrossRepoHop]
  diagnostics : list[str]

TraversalHop
  hop_number : int
  from_node_id : str
  to_node_id : str
  via_interface_id : str
  plugin_id : str
  edge_type : str
  confidence : ConfidenceLevel
  operation_name : str | None
  repo_boundary_crossed : bool
  language_boundary_crossed : bool

AmbiguousCandidate
  hop_number : int
  from_node_id : str
  candidate_node_ids : list[str]
  plugin_id : str
  reason : str
  confidence : ConfidenceLevel

CrossRepoHop
  from_repo_id : str
  to_repo_id : str
  via_interface_id : str
  plugin_id : str
```

### 8.4 Traversal Algorithm

The traversal is a bounded BFS over cross-language edges in the graph store:

1. Initialize visited set with `start_node_id`.
2. Initialize queue with `start_node_id`.
3. While queue is not empty and hop count < `max_hops`:
   - Dequeue current node.
   - For each registered available plugin:
     - Call `plugin.traverse(current_node_id, direction, graph_store)`.
     - For each returned `TraversalLink`:
       - If `link.confidence` below `min_confidence`, add to `ambiguous_candidates` and skip.
       - If target not in visited, add to visited and queue, record hop.
       - If target is in a different repo, record as `cross_repo_hop`.
4. Return `CrossLanguageTraversalResult`.

Rules:

- Traversal is purely graph-read. No source file parsing at query time.
- A node may appear in only one hop as target to prevent cycles.
- Ambiguous candidates (low-confidence links) are reported but not traversed by default.
- Cross-repo hops require both repos to be registered.

### 8.5 Traversal Integration With `find_callers` And `find_callees`

When `find_callers` or `find_callees` is called with `include_cross_language=True`:

- After collecting same-language callers/callees from the graph, invoke the traversal engine.
- For `find_callers`: also find all nodes that `consume` an interface this node `exposes`.
- For `find_callees`: also find all nodes this node's callsite `consumes` that have `implements` or `exposes` handlers.
- Merge results with appropriate confidence levels.
- Emit a capability diagnostic when a plugin that would have been useful is unavailable.

### 8.6 Traversal Tests

Required tests:

- Single-hop traversal across HTTP-REST boundary.
- Multi-hop traversal (Python → HTTP → TS → WebSocket).
- Max-hop limit terminates traversal.
- Ambiguous candidate is reported but not traversed.
- Cross-repo hop detected and reported.
- Cycle prevention: visited set prevents infinite loop.
- Empty traversal (no plugins registered) returns zero hops.
- Confidence cutoff filters low-confidence links from traversal.

---

## 9. HTTP-REST Plugin

### 9.1 Purpose

The HTTP-REST plugin links server-side route handlers (Python: FastAPI, Flask, Django) to client-side HTTP callsites (JavaScript/TypeScript: fetch, axios, and similar libraries) via a canonical URL path representation.

### 9.2 Detection

`detect` looks for:

- Files with OpenAPI/Swagger content: `openapi.yaml`, `openapi.json`, `swagger.yaml`, `swagger.json`, files with `openapi:` or `swagger:` top-level key.
- Python files with route decorator patterns: `@app.get`, `@app.post`, `@router.get`, `@app.route`, `@blueprint.route`, `path(...)` in `urls.py`.
- TypeScript/JavaScript files with HTTP client patterns: `fetch(`, `axios.get(`, `axios.post(`, `new XMLHttpRequest`.

Confidence of detection:

- OpenAPI file found: `parser`.
- Route decorator found in Python: `analyser`.
- HTTP client pattern found in TS/JS: `analyser`.

### 9.3 OpenAPI/Swagger Parser

`openapi_parser.py` parses OpenAPI 3.x and Swagger 2.x documents.

Extracts per path and method:

- HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS).
- Canonical path pattern (normalized via URL normalizer).
- Operation ID where present.
- Request body schema.
- Response schemas per status code.
- Path, query, header, and cookie parameters.
- Security scheme hints.
- Tags as grouping metadata.

Rules:

- Parse both YAML and JSON.
- OpenAPI 3.x and Swagger 2.x schemas are both supported.
- Unknown OpenAPI versions produce a typed diagnostic, not a crash.
- Schema `$ref` references within the same document are resolved before extraction.
- External `$ref` to other files is treated as unresolved (low confidence) with a diagnostic.

### 9.4 FastAPI Route Detector

`fastapi_detector.py` uses Phase 3/5 Python AST to detect FastAPI route declarations.

Detection pattern:

- Functions/coroutines decorated with `@app.get(...)`, `@app.post(...)`, `@router.get(...)`, etc.
- The decorator's first positional argument is the path pattern.
- The function is the handler node.
- Parameter types infer the path/query/body schema where type annotations are present.

Extraction:

- HTTP method from decorator name.
- Path from decorator first argument.
- Handler function graph node ID from Phase 5 Python AST index.
- Parameter names and type annotations for input schema hints.
- Response model from `response_model=...` keyword where present.

### 9.5 Flask Route Detector

`flask_detector.py` uses Phase 5 Python AST.

Detection pattern:

- Functions decorated with `@app.route(path, methods=[...])` or `@blueprint.route(...)`.
- `methods` argument defaults to `["GET"]` when absent.
- Variable rules in Flask paths: `<int:user_id>`, `<string:name>`, `<path:subpath>`.

Path normalization: Flask `<int:user_id>` → canonical `{user_id}`.

### 9.6 Django URL Detector

`django_detector.py` uses Phase 5 Python AST to detect Django URL patterns.

Detection pattern:

- Scan `urls.py` files (or files matching `*_urls.py`, `*urls*.py`).
- Find assignments to `urlpatterns`.
- Parse `path(route, view, name=...)` and `re_path(pattern, view)` calls.
- Resolve view to a callable (function or class-based view's `as_view()`).
- Resolve `include(...)` to point to sub-URL files.

Limitations and diagnostics:

- `re_path` with complex regex: emit as heuristic-confidence with the raw regex.
- `include(...)` to external module: emit as unresolved cross-module include diagnostic.

### 9.7 JS/TS Client Detector

`client_detector.py` uses Phase 5 TypeScript ts-morph adapter output to detect HTTP client callsites.

Detection patterns:

- `fetch(url, { method: 'GET' })` — native Fetch API.
- `axios.get(url, config)`, `axios.post(url, data, config)` — Axios.
- `http.get(url, callback)` — Node.js `http` module.
- `request(url, options)` — `request` / `superagent` / similar libraries.

URL extraction:

- String literal URL: exact, high confidence.
- Template literal URL with static prefix: inferred confidence.
- Variable URL: low confidence, emit as ambiguous candidate with the variable source.

Canonical URL normalization applied to all extracted URLs.

### 9.8 URL Normalizer

`url_normalizer.py` maps URL path patterns from different styles to a single canonical form.

Normalization rules:

| Input style | Example | Canonical form |
|---|---|---|
| Express.js | `/users/:id` | `/users/{id}` |
| Flask typed | `/users/<int:id>` | `/users/{id}` |
| Flask untyped | `/users/<id>` | `/users/{id}` |
| OpenAPI 3.x | `/users/{id}` | `/users/{id}` |
| Django | `users/<int:pk>/` | `/users/{pk}` |
| Trailing slash | `/users/` | `/users` |
| Double slash | `/users//profile` | `/users/profile` |

Additional rules:

- Lowercase scheme and host if present.
- Strip query string before normalization.
- Preserve the canonical form as the `path_pattern` field.
- Store the original raw pattern alongside the canonical form.

Matching two patterns:

- Exact canonical match: `confirmed` link.
- Canonical match with different parameter names but same structure: `inferred` link.
- Path prefix match (one pattern is a prefix of the other): `ambiguous` candidate.

### 9.9 Schema Extractor

`schema_extractor.py` derives request/response schema hints for routes detected without OpenAPI.

Sources:

- Python type annotations on handler function parameters (Pydantic models, dataclasses, simple types).
- TypeScript parameter types at callsites (when ts-morph resolves them).
- Inline `request.json`, `request.get_json()`, or `body` variable usage hints.

Output: partial JSON Schema as a `dict` with `confidence=heuristic`.

When OpenAPI schema is available, use it directly as `confidence=parser`.

### 9.10 HTTP-REST Plugin Orchestration

`plugin.py` orchestrates detect → index → link:

1. Detect: scan for OpenAPI files and framework route patterns.
2. Index: parse OpenAPI if found; fall back to AST detectors.
3. Link:
   - Emit `http_route` graph nodes for each route operation.
   - Emit `exposes` edges from handler function nodes to `http_route` nodes.
   - Emit `consumes` edges from client callsite nodes to matched `http_route` nodes.
   - Ambiguous client URLs become low-confidence `consumes` edges.
4. Emit `InterfaceRecord` per path prefix group.

### 9.11 HTTP-REST Plugin Tests

Required tests:

- OpenAPI YAML parse produces routes with method, path, and schema.
- Swagger 2.x JSON parse produces routes.
- FastAPI `@app.get("/users/{id}")` → `http_route` node and `exposes` edge to handler node.
- Flask `@app.route("/users/<int:user_id>", methods=["GET"])` → `http_route` node.
- Django `path("users/<int:pk>/", view)` → `http_route` node.
- TS `fetch("/api/users/1")` → `consumes` edge to matched `http_route`.
- URL normalization: `<int:id>`, `{id}`, `:id` all match canonical `/users/{id}`.
- Ambiguous dynamic URL → low-confidence candidate.
- Unmatched client URL → diagnostic.
- Missing framework (no FastAPI installed): detection degrades gracefully.
- `trace_cross_language` follows HTTP boundary from Python handler to TS client.

---

## 10. WebSocket Plugin

### 10.1 Purpose

The WebSocket plugin links server-side event handlers (Python socket.io) to client-side event emitters and listeners (TypeScript socket.io-client), matching by event name and namespace.

### 10.2 Detection

`detect` looks for:

- Python: files importing `flask_socketio`, `socketio`, `python_socketio`, `fastapi_socketio`.
- Python: `@socketio.on(...)`, `emit(...)` patterns.
- TypeScript/JavaScript: files importing `socket.io-client`, `socket.io`.
- TypeScript: `socket.on(...)`, `socket.emit(...)` patterns.

### 10.3 Server Detector

`server_detector.py` uses Phase 5 Python AST to extract event registrations.

Detection patterns:

- `@socketio.on('event_name')` decorator on a handler function.
- `@socketio.on('event_name', namespace='/ns')` with explicit namespace.
- `sio.on('event_name', handler_function)` programmatic registration.
- `socketio.emit('event_name', data, ...)` emission site.
- `emit('event_name', data)` within a handler context.

Extraction:

- Event name: static string literal → exact confidence.
- Event name: computed/variable → low-confidence candidate with variable source noted.
- Namespace: explicit string → recorded; implicit → default namespace `/`.
- Handler function graph node ID from Phase 5 AST index.

### 10.4 Client Detector

`client_detector.py` uses Phase 5 TypeScript ts-morph output.

Detection patterns:

- `socket.on('event_name', callback)` — event listener.
- `socket.emit('event_name', data)` — event emitter.
- `io.on('connect', ...)` — lifecycle events (recorded separately as metadata).
- `socket.off('event_name')` — deregistration noted as metadata.
- Namespace construction: `io('/namespace')` or `socket.nsp`.

Extraction:

- Event name: static string or template literal with static prefix → analyser confidence.
- Event name: dynamic → heuristic candidate.
- Payload type: TypeScript type annotation where available → recorded as `output_schema` hint.

### 10.5 Event Extractor

`event_extractor.py` normalizes and deduplicates events from server and client sides.

Rules:

- Events with exact name match and same namespace: `confirmed` link.
- Events with matching name but no explicit namespace on one side: `inferred` link (default namespace assumed).
- Events with partial static prefix: `ambiguous` candidate.
- Dynamic event names: always `ambiguous` candidate unless the finite set can be proven.

### 10.6 Namespace Resolver

`namespace_resolver.py` resolves socket.io namespaces.

Rules:

- Explicit namespace `/chat` on server and `io('/chat')` on client → exact match.
- Implicit namespace on one side and explicit `/` on the other → match.
- Different explicit namespaces → no match; emit diagnostic.

### 10.7 Payload-Shape Hints

Payload-shape hints are extracted from:

- TypeScript interface types on callback parameters.
- Pydantic model or dataclass annotations in Python handler signatures.
- JSON-schema literals in event handler code.

Rules:

- Hints are stored as `input_schema` / `output_schema` on `InterfaceOperation`.
- Hints are `heuristic` confidence unless derived from an explicit type annotation.
- Mismatched schemas between server and client sides are recorded as a `SCHEMA_MISMATCH` diagnostic.

### 10.8 WebSocket Plugin Orchestration

`plugin.py`:

1. Detect: find socket.io imports in Python and TS files.
2. Index: extract events from server and client detectors.
3. Link:
   - Emit `websocket_event` nodes for each unique event name + namespace.
   - Emit `exposes` edges from server handler function nodes.
   - Emit `consumes` edges from client callsite nodes.
4. Emit one `InterfaceRecord` per namespace.

### 10.9 WebSocket Plugin Tests

Required tests:

- `@socketio.on('message')` → `websocket_event` node and `exposes` edge.
- `socket.emit('message', data)` in TS → `consumes` edge to matched event node.
- Same namespace match: `confirmed`.
- Dynamic event name on server: `ambiguous` candidate.
- TS TypeScript type annotation on callback: recorded as input schema hint.
- Namespace mismatch: diagnostic.
- `trace_cross_language` follows WebSocket boundary from Python handler to TS listener.

---

## 11. omniORB-IDL Plugin

### 11.1 Purpose

The omniORB-IDL plugin links CORBA IDL interface definitions to their C++ servant implementations (via libclang) and to their Python stub modules and callers (via pyan3 and import resolver).

### 11.2 Detection

`detect` looks for:

- Files with `.idl` extension.
- Files containing CORBA IDL keywords: `interface`, `module`, `typedef`, `sequence`, `in`, `out`, `inout`, `raises` in a syntactic pattern.

### 11.3 IDL Parser

`idl_parser.py` extracts the IDL AST from omniIDL.

Primary path:

- Invoke `omniidl -p <tempdir> <file.idl>` to write a Python-format IDL dump.
- Parse the dump to extract module names, interface names, and method signatures.

Fallback path (when `omniidl` is not installed):

- Use a hand-written IDL tokenizer for basic interface/method extraction.
- Mark as `heuristic` confidence with a diagnostic recommending `omniidl` installation.

Extracts:

- Module hierarchy.
- Interface names and inheritance.
- Method names, parameter names, types, directions (`in`, `out`, `inout`), and return types.
- Exception specifications from `raises(...)`.
- Oneway operations.

Emits `idl_interface` graph nodes and one `InterfaceOperation` per IDL method.

### 11.4 C++ Servant Linker

`cpp_servant_linker.py` uses Phase 5 libclang output to find servant implementations.

Steps:

1. From the IDL interface name (e.g., `Calculator`), compute the expected POA class name: `POA_Calculator`.
2. Query the Phase 5 C++ graph for class nodes whose name matches `POA_Calculator` or inherits from it.
3. For each matched class, find methods with the same signature as IDL methods.
4. Emit `implements` edges from the C++ servant class to the `idl_interface` node.
5. Emit `ffi` edges from C++ method nodes to IDL operation nodes.

Confidence:

- Exact POA class name match + method signature match: `parser`.
- POA class name match only: `analyser`.
- Heuristic name/inheritance match: `heuristic`.

Generated file rules:

- Detect `*SK.cc`, `*_skel.cc`, and similar generated skeleton files from `omniidl`.
- Mark their `file` nodes as `generated=True`.
- Emit `GeneratedArtifactRecord` for each skeleton file.
- Do not recommend editing generated skeletons in patch review or blast-radius.

### 11.5 Python Stub Linker

`python_stub_linker.py` uses Phase 5 Python import resolver and pyan3 output.

Steps:

1. Locate Python stub files generated by `omniidl`: files matching `*_idl.py`, `*CORBA_idl.py`, or files under directories with `omniidl`-style naming.
2. Mark these as generated artifacts.
3. Query the Phase 5 Python graph for import edges pointing to these stub modules.
4. Emit `consumes` edges from Python callers to the `idl_interface` node.
5. Emit `ffi` edges from Python stub module nodes to IDL operation nodes.

Confidence:

- Exact import + method call resolution via pyan3: `parser`.
- Import present but method call unresolved: `analyser`.

### 11.6 Caller Finder

`caller_finder.py` finds Python code that calls IDL methods through the generated stubs.

Steps:

1. Locate stub method nodes (Phase 5 Python graph) in stub modules.
2. Use pyan3 call edges from those method nodes to find all calling functions.
3. Record callers as `client_callsite_node_ids` in the `InterfaceOperation`.
4. Emit `consumes` edges from callers to the IDL operation node.

### 11.7 Generated Artifact Tracker

`generated_artifact_tracker.py` maintains the list of generated files for this plugin and enforces the no-manual-edit policy.

Rules:

- Generated files are tagged in the graph node with `generated=True` and `generator_tool=omniidl`.
- When a generated file is detected as modified (Phase 3 incremental update), emit a warning recommending IDL-level changes instead.
- `GeneratedArtifactRecord` includes the regeneration command for documentation.

### 11.8 omniORB-IDL Plugin Orchestration

`plugin.py`:

1. Detect: find `.idl` files.
2. Index: parse IDL, extract interface and method records.
3. Link:
   - Find C++ POA skeletons and servant implementations.
   - Find Python stub modules.
   - Find Python callers.
   - Emit `idl_interface` nodes, `implements` edges (C++ servant → IDL), `ffi` edges, and `consumes` edges (Python callers → IDL).
   - Mark generated stubs.
4. Emit `InterfaceRecord` per IDL interface.

### 11.9 omniORB-IDL Plugin Tests

Required tests:

- IDL parse extracts interface name, method names, and parameter types.
- `omniidl` unavailable: fallback tokenizer used, `heuristic` confidence noted.
- C++ servant linker finds `POA_Calculator` class and emits `implements` edge.
- Generated skeleton file `calculatorSK.cc` marked as `generated=True`.
- Python stub module `calculator_idl.py` marked as `generated=True`.
- Python caller found via pyan3: `consumes` edge emitted.
- `trace_cross_language` follows IDL boundary: Python caller → IDL → C++ servant.
- `ffi` edge present between Python stub and IDL operation.
- Manual edit to generated stub file produces warning diagnostic.

---

## 12. Plugin Extension Backlog

### 12.1 Purpose

Section 12 defines the registration point and stub structure for future plugins. These stubs ensure the plugin registry slot is reserved and future implementations know the expected interface.

### 12.2 Backlog Plugin Stubs

Each backlog stub in `plugins/backlog/` must:

- Define a class implementing `InterfacePluginBase`.
- Return `available=False` from `check_availability` with reason `not_yet_implemented`.
- Return a complete `PluginCapabilityDescriptor` describing the intended future capability.
- Raise `NotImplementedError` from `detect`, `index`, `link`, and `traverse`.

### 12.3 Planned Plugins

| Plugin stub | Interface type | Planned server languages | Planned client languages |
|---|---|---|---|
| `GrpcStub` | gRPC services (`.proto` files) | Python, C++, Go | Python, TypeScript |
| `ProtobufStub` | Protobuf message types | All gRPC participants | All gRPC participants |
| `ZeroMQStub` | ZeroMQ sockets | Python, C++ | Python, TypeScript |
| `MqttStub` | MQTT topics | Python, C++ | Python, TypeScript |
| `DbusStub` | D-Bus service interfaces | Python, C++ | Python |

### 12.4 Adding A New Plugin

Adding a new plugin must not require modifying any existing plugin, the core server, or the graph schema. A new plugin author must:

1. Create a new module under `plugins/`.
2. Implement `InterfacePluginBase`.
3. Register the plugin in the workspace configuration or auto-discovery path.
4. Add tests following the pattern of existing plugin test modules.
5. Add the plugin to the capability report and update the plugin inventory in `AGENTS.md`.

### 12.5 Backlog Tests

Required tests:

- Each backlog stub returns `available=False`.
- Each backlog stub returns a non-empty capability descriptor.
- Registering a backlog stub does not affect traversal results from implemented plugins.

---

## 13. `trace_cross_language` MCP Tool

### 13.1 Purpose

`trace_cross_language` follows a call chain from a starting symbol through all registered interface plugins and returns an ordered list of reached nodes across languages and repositories.

### 13.2 Tool Input

```text
trace_cross_language input
  repo : str                         # Start repo ID
  symbol : str                       # Start symbol node ID, path, or qualified name
  direction : str | None             # outbound, inbound, both; default both
  max_hops : int | None              # Default 10
  plugins : list[str] | None         # None = all registered
  min_confidence : str | None        # heuristic, analyser, parser; default heuristic
  snapshot : str | None              # Specific snapshot; default current
  include_ambiguous : bool | None    # Include low-confidence candidates; default False
```

### 13.3 Tool Output

```text
trace_cross_language output
  start_node_id : str
  start_symbol_path : str
  hops : list[TraversalHop]
  total_hops : int
  languages_visited : list[str]
  repos_visited : list[str]
  cross_repo_hops : list[CrossRepoHop]
  ambiguous_candidates : list[AmbiguousCandidate]
  terminated_early : bool
  termination_reason : str | None
  diagnostics : list[str]
  run_event_ids : list[str]
  snapshot_ids : dict[str, str]
```

### 13.4 Tool Behavior

1. Resolve `symbol` to a graph node ID via symbol lookup.
2. Verify snapshot freshness for all involved repos.
3. Call `CrossLanguageTraverser.traverse(...)`.
4. Format result and emit run event.

### 13.5 Snapshot Consistency

Rules:

- If different repos involved in a traversal have different snapshot ages, emit a `MIXED_SNAPSHOT` diagnostic.
- Stale snapshots produce a warning but do not block traversal.
- Each hop carries the snapshot ID of its source node.

### 13.6 Permission Descriptor

```text
required_mode : read/search
path_scope : registered repos
network_requirement : none
side_effect_class : read_only (telemetry only)
approval_requirement : not required
allowed_stages : S1 and above
```

### 13.7 `trace_cross_language` Tests

Required tests:

- Traversal from Python handler crosses HTTP boundary to TS client.
- Traversal from Python caller crosses IDL boundary to C++ servant.
- Traversal with `max_hops=1` terminates after one hop.
- Unknown start symbol returns typed error.
- No plugins registered: zero hops, capability diagnostic.
- Cross-repo traversal follows link when both repos are registered.
- Ambiguous candidates excluded unless `include_ambiguous=True`.
- Snapshot consistency warning on mixed-age snapshots.

---

## 14. `plugin_reload` MCP Tool

### 14.1 Purpose

Phase 4 implemented `plugin_reload` as a no-op stub returning `not_implemented_until_phase_7`. Phase 7 graduates it to a working implementation that re-runs a plugin's detect/index/link pipeline and emits appropriate notifications.

### 14.2 Tool Input

```text
plugin_reload input
  plugin_id : str | None        # None = reload all registered available plugins
  repo_ids : list[str] | None   # None = all registered repos
  task : bool | None
```

### 14.3 Tool Output

```text
plugin_reload output
  plugins_reloaded : list[str]
  repos_reloaded : list[str]
  interface_records_updated : int
  nodes_added : int
  edges_added : int
  nodes_removed : int           # Interfaces no longer detected after reload
  diagnostics : list[str]
  notifications_emitted : list[str]
  run_event_ids : list[str]
```

### 14.4 Tool Behavior

1. Validate plugin IDs.
2. For each `(plugin, repo)` pair:
   - Run `plugin.detect(repo, snapshot, file_list)`.
   - Run `plugin.index(repo, snapshot, detect_result, config)`.
   - Diff against prior `PluginIndexResult` to detect changed/added/removed interfaces.
   - Run `plugin.link(repo, snapshot, index_result, graph_store, config)`.
   - Update graph nodes and edges.
   - Emit `notifications/resources/updated` for changed interface resources.
   - Emit `notifications/resources/list_changed` if interface list changed.
3. Update plugin run record in operational store.
4. Return aggregate result.

### 14.5 Removal Of Stale Interface Links

When a plugin is reloaded and an interface record no longer exists:

- Mark its graph nodes as superseded.
- Remove or supersede its `exposes`, `consumes`, `implements`, and `ffi` edges.
- Record the removal in the operational ledger.
- Emit a `notifications/resources/list_changed` notification.

### 14.6 Task Support

`plugin_reload` is task-capable for full multi-plugin, multi-repo reloads.

### 14.7 Permission Descriptor

```text
required_mode : execute (re-runs analysis subprocess for some plugins)
path_scope : registered repo roots
network_requirement : none
side_effect_class : writes_graph_nodes, writes_graph_edges, writes_plugin_store
approval_requirement : not required by default
```

### 14.8 `plugin_reload` Tests

Required tests:

- Single plugin reload updates interface records.
- Removed interface: nodes superseded, edges removed, list-changed notification.
- New interface detected: nodes added, list-changed notification.
- All-plugin reload iterates all available plugins.
- Unavailable plugin skipped with diagnostic.
- Task creation for full multi-plugin reload.
- Notifications emitted for each changed interface resource.

---

## 15. Interface MCP Resources

### 15.1 `code-intelligence://interfaces`

Purpose: list all registered interface plugins and the interfaces they have indexed.

Payload:

```text
InterfaceListResource
  plugins : list[PluginSummary]
  total_interface_records : int
  last_indexed_ts : str | None
  schema_version : str

PluginSummary
  plugin_id : str
  plugin_version : str
  interface_kind : str
  available : bool
  interface_count : int
  repos_indexed : list[str]
  last_indexed_ts : str | None
```

Rules:

- Subscribable. List changes when plugins are registered, unregistered, or reloaded.
- `notifications/resources/list_changed` fires when plugin count or interface count changes.

### 15.2 `code-intelligence://interfaces/{plugin_id}/{interface_name}`

Purpose: serve the full `InterfaceRecord` for a named interface.

Payload: `InterfaceRecord` with operations, server/client node IDs, generated artifact refs, confidence, and provenance.

Rules:

- Subscribable. `notifications/resources/updated` fires after `plugin_reload` changes the record.
- `interface_name` is URL-encoded.
- Unknown `plugin_id` or `interface_name` returns typed not-found.
- Large `operations` lists may be paginated or offered as artefact references.

### 15.3 Interface Resource List Handler

List handler for `code-intelligence://interfaces/{plugin_id}`:

- Lists all interface names indexed by a given plugin for all repos.
- Payload: `list[InterfaceNameEntry]` with `interface_id`, `interface_name`, `kind`, `repo_ids`, and `last_indexed_ts`.

### 15.4 Resource Descriptor Rules

- `interfaces` resource is listable and subscribable.
- `interfaces/{plugin_id}/{interface_name}` is readable and subscribable.
- Resource reads return freshness/snapshot metadata.
- Missing plugin returns `ResourceNotFound` with available plugin IDs in the diagnostic.

### 15.5 Resource Tests

Required tests:

- List resource returns all registered plugins and interface counts.
- Single interface resource returns full `InterfaceRecord`.
- Subscription fires after `plugin_reload`.
- List-changed fires when interface count changes.
- Unknown plugin_id: typed not-found.
- Unknown interface_name: typed not-found.
- `plugin_id` list resource enumerates interfaces for that plugin.

---

## 16. Traversal Integration With Existing Graph Tools

### 16.1 `find_callers` With Cross-Language

When `find_callers(symbol, include_cross_language=True)`:

- Execute same-language caller lookup as before.
- Additionally: for each interface the symbol's node `exposes`, find all client nodes that `consume` that interface.
- For each interface the symbol's method `implements` via IDL, find all Python callers that `consume` the IDL operation.
- Merge results with `cross_language=True` annotation per result.

### 16.2 `find_callees` With Cross-Language

When `find_callees(symbol, include_cross_language=True)`:

- Execute same-language callee lookup as before.
- Additionally: for each `consumes` edge from this symbol's callsites, find the `http_route`, `websocket_event`, or `idl_interface` node, then follow `exposes` or `implements` edges to the server-side handlers.
- Merge results with `cross_language=True` annotation.

### 16.3 `get_graph_slice` With Interface Edges

When `edge_types` includes `implements`, `exposes`, `consumes`, or `ffi`:

- Include the matched interface node and its linked implementation nodes in the slice.
- Include `InterfaceOperation` nodes as connected to the interface node.
- Flag ambiguous links in slice diagnostics.

### 16.4 Integration Rules

- Cross-language traversal is opt-in per tool call via `include_cross_language`.
- When cross-language is enabled but no plugins are registered, emit a capability diagnostic rather than failing.
- Cross-language results carry the plugin_id and confidence of each link.
- Phase 4 `find_callers` and `find_callees` already return capability diagnostics for unavailable cross-language traversal; this phase replaces those diagnostics with real results where plugins are registered.

---

## 17. Confidence Model For Interface Links

### 17.1 Exact Links

Confidence `parser` for:

- OpenAPI-matched route where the handler is unambiguously identified via Python AST.
- IDL method linked to a C++ servant method with matching signature via libclang.
- socket.io static event name on both server and client sides.
- Python caller of a stub method resolved via pyan3 with full module path.

### 17.2 Inferred Links

Confidence `analyser` for:

- Framework-detected route (FastAPI/Flask/Django AST) without an OpenAPI file to confirm.
- socket.io event name matched across server and client by name only, no payload schema comparison.
- IDL method linked to C++ servant by class name only, without method signature verification.
- HTTP client call with static URL string but no OpenAPI to confirm the server path.

### 17.3 Ambiguous Links

Confidence `heuristic` for:

- Dynamic URL construction in HTTP clients.
- Dynamic event names in socket.io.
- Python callers of stub methods unresolved by pyan3 (import present but call edge absent).
- C++ class matching POA name pattern but without verified method signatures.
- Partial URL prefix match between client and server.

### 17.4 No-Link Cases

Do not emit a link when:

- The URL or event name is entirely dynamic with no static component.
- No matching server handler is found for a client callsite.
- The IDL interface references a module not found in any registered repo.

Emit a diagnostic for each no-link case instead.

### 17.5 Cross-Repo Confidence

Cross-repo links carry the same confidence as same-repo links, with an additional `cross_repo=True` flag. Both repos must be registered for a cross-repo link to be emitted.

---

## 18. Incremental Update And Plugin Re-Index

### 18.1 Trigger Conditions

A plugin re-index is needed when:

- An IDL file changes: full omniORB-IDL plugin re-index for the affected repo.
- An OpenAPI/Swagger file changes: full HTTP-REST plugin re-index for that repo.
- A Python route handler file changes: HTTP-REST and WebSocket partial re-index.
- A TypeScript client file changes: HTTP-REST and WebSocket partial re-index.
- A C++ servant implementation file changes: omniORB-IDL servant linker re-run.
- A Python stub module changes: omniORB-IDL stub linker re-run (and a generated-file-modified warning).

### 18.2 Integration With `graph_update`

`graph_update` must:

- Check which Phase 7 plugin-relevant files have changed.
- Trigger affected plugin detect/index/link passes for changed file subsets where plugins support incremental.
- Update interface records, graph nodes, and edges.
- Emit resource update notifications for changed interface resources.

### 18.3 Invalidation

When a plugin re-index removes an interface operation:

- Mark the old `http_route`, `websocket_event`, or `idl_interface` node as superseded.
- Supersede its `exposes`, `consumes`, `implements`, and `ffi` edges.
- Emit resource update notification.

### 18.4 Incremental Tests

Required tests:

- IDL file change: plugin re-index updates IDL interface and linked servant.
- OpenAPI file change: route records updated.
- Generated stub modified: warning emitted.
- Old interface node superseded after interface removal.
- `graph_update` triggers plugin re-index for changed interface definition files.

---

## 19. Security, Privacy, And Generated Artifact Rules

### 19.1 Path Safety

Rules:

- All file paths from plugin detection must be validated as repo-relative.
- `detect` must not accept absolute paths from external input.
- URL normalization must not execute URL or resolve HTTP requests.
- omniIDL subprocess invocation must use explicit argument lists (no shell=True).

### 19.2 External Document Trust

Rules:

- OpenAPI/Swagger files are parsed as data; no code execution from `info.x-code` fields.
- IDL files are parsed through `omniidl` subprocess, not `eval`.
- Schema definitions in OpenAPI are stored as-is; they are not executed as validators during indexing.

### 19.3 Generated Artifact Protection

Rules:

- No plugin may emit a patch recommendation targeting a generated file.
- `GeneratedArtifactRecord.file_paths` must be excluded from blast-radius recommended-fix paths.
- When Phase 11 patch review detects a diff touching a generated file, it must flag it and recommend changing the source interface definition.

### 19.4 Cross-Repo Privacy

Rules:

- Interface records that link symbols across two registered repos must carry both repo IDs in provenance.
- Do not expose cross-repo links to clients that have only authorized access to one repo. Phase 7 enforces this by checking authorization context for both repos when a cross-repo link is returned.

---

## 20. Test Plan

### 20.1 Plugin Base Tests

Required:

- `InterfacePluginBase` contract tests via a minimal no-op test plugin.
- `check_availability` fast and side-effect-free.
- `detect` with empty file list returns empty result.
- `PluginLinkResult` validates against Phase 1 schema.

### 20.2 Registry Tests

Required:

- Register, unregister, duplicate detection.
- Availability filter.
- Capability report snapshot.

### 20.3 HTTP-REST Plugin Tests

Required:

- OpenAPI parse (3.x YAML, 2.x JSON).
- FastAPI, Flask, Django route detection.
- TS client detection (fetch, axios).
- URL normalization across four styles.
- `exposes` and `consumes` edges.
- Ambiguous dynamic URL → candidate.
- Traversal from Python handler to TS client.

### 20.4 WebSocket Plugin Tests

Required:

- socket.io server event detection.
- socket.io client detection.
- Static event name match.
- Dynamic event name → candidate.
- Namespace mismatch diagnostic.
- Traversal from Python handler to TS listener.

### 20.5 omniORB-IDL Plugin Tests

Required:

- IDL parse (with and without `omniidl`).
- C++ servant link.
- Python stub link.
- Caller detection via pyan3.
- Generated file marking.
- Traversal from Python caller to C++ servant.

### 20.6 Traversal Engine Tests

Required:

- Single-hop, multi-hop, max-hop termination.
- Cycle prevention.
- Ambiguous candidate reporting.
- Cross-repo hop detection.
- Confidence cutoff filtering.

### 20.7 MCP Tool Tests

Required:

- `trace_cross_language` returns ordered hops.
- `plugin_reload` updates records and emits notifications.
- Stale interface removal after reload.
- Task creation for reload.

### 20.8 Resource Tests

Required:

- Interface list resource.
- Single interface resource.
- Subscriptions and notifications.
- Not-found for unknown plugin/name.

### 20.9 Integration Tests

Required:

- HTTP-REST: `find_callers` with `include_cross_language=True` returns TS client.
- IDL: `find_callees` from Python caller returns C++ servant.
- Mixed: multi-hop traversal Python → HTTP → TS → WebSocket → Python.
- `get_graph_slice` with `exposes`/`consumes` edge types includes interface nodes.

### 20.10 Regression Tests

Required:

- Plugin capability descriptor snapshots.
- `trace_cross_language` tool descriptor snapshot.
- `plugin_reload` tool descriptor snapshot.
- Interface resource descriptor snapshot.

---

## 21. Work Packages

### P7.1 Plugin Base Interface And Registry

Build:

- `InterfacePluginBase` abstract class.
- `PluginDetectResult`, `PluginIndexResult`, `PluginLinkResult`, `TraversalLink`.
- `PluginCapabilityDescriptor` and `PluginAvailability`.
- `PluginRegistry`.

Deliverables:

- `plugins/base.py`, `plugins/registry.py`, `plugins/capability.py`, `plugins/errors.py`
- Base and registry tests.

Acceptance:

- Interface contract tests pass for a no-op test plugin.

### P7.2 InterfaceRecord Model

Build:

- `InterfaceRecord`, `InterfaceOperation`, `OperationParameter`.
- `InterfaceKind` enum.
- `GeneratedArtifactRecord`.
- Phase 1 schema validation integration.

Deliverables:

- `plugins/interface_record.py`
- Model tests.

Acceptance:

- `InterfaceRecord` round-trips through Phase 1 schema validation.

### P7.3 Cross-Language Traversal Engine

Build:

- `CrossLanguageTraverser`.
- `CrossLanguageTraversalResult`, `TraversalHop`, `AmbiguousCandidate`.
- BFS algorithm with hop bound and cycle prevention.

Deliverables:

- `plugins/traversal.py`
- Traversal tests.

Acceptance:

- Single-hop and multi-hop traversal work with test plugin.

### P7.4 HTTP-REST Plugin

Build:

- OpenAPI/Swagger parser.
- FastAPI, Flask, Django detectors.
- JS/TS client detector.
- URL normalizer.
- Schema extractor.
- Plugin orchestrator.
- HTTP-REST fixture repo.

Deliverables:

- `plugins/http_rest/`
- HTTP-REST fixture files.
- HTTP-REST plugin tests.

Acceptance:

- `trace_cross_language` crosses HTTP boundary in fixture.

### P7.5 WebSocket Plugin

Build:

- Server detector.
- Client detector.
- Event extractor.
- Namespace resolver.
- Plugin orchestrator.
- WebSocket fixture repo.

Deliverables:

- `plugins/websocket/`
- WebSocket fixture files.
- WebSocket plugin tests.

Acceptance:

- `trace_cross_language` crosses WebSocket boundary in fixture.

### P7.6 omniORB-IDL Plugin

Build:

- IDL parser (omniidl + fallback tokenizer).
- C++ servant linker.
- Python stub linker.
- Caller finder.
- Generated artifact tracker.
- Plugin orchestrator.
- omniORB fixture repo.

Deliverables:

- `plugins/omniorb_idl/`
- omniORB-IDL fixture files.
- omniORB-IDL plugin tests.

Acceptance:

- `trace_cross_language` crosses IDL boundary from Python to C++ in fixture.

### P7.7 Plugin Backlog Stubs

Build:

- gRPC, Protobuf, ZeroMQ, MQTT, DBUS stubs.
- Capability descriptors for each.

Deliverables:

- `plugins/backlog/`
- Backlog stub tests.

Acceptance:

- All stubs return `available=False`.

### P7.8 `trace_cross_language` MCP Tool

Build:

- Tool handler.
- Symbol resolution.
- Traversal engine integration.
- Permission descriptor.
- Telemetry.

Deliverables:

- `mcp_server/tools/interface.py` (trace_cross_language handler).
- Tool tests.

Acceptance:

- MCP client can call `trace_cross_language` and receive ordered hops.

### P7.9 `plugin_reload` MCP Tool (Graduating From Phase 4 Stub)

Build:

- Working reload pipeline.
- Diff against prior index.
- Node/edge supersession.
- Task support.
- Notification emission.

Deliverables:

- `plugin_reload` handler in `mcp_server/tools/interface.py`.
- Reload tests.

Acceptance:

- `plugin_reload` updates records, supersedes stale nodes, and emits notifications.

### P7.10 Interface MCP Resources And Regression Tests

Build:

- `code-intelligence://interfaces` list resource.
- `code-intelligence://interfaces/{plugin_id}/{interface_name}` resource.
- `code-intelligence://interfaces/{plugin_id}` enumeration resource.
- Subscription integration.
- Tool and resource regression tests.

Deliverables:

- `mcp_server/resources/interfaces.py`
- Resource tests.
- Regression test harness additions.

Acceptance:

- MCP client reads interface resource and receives update notification after `plugin_reload`.

---

## 22. Suggested Implementation Order

Recommended order:

1. Plugin base interface, `InterfaceRecord` model, and plugin registry.
2. Cross-language traversal engine with no-op test plugin.
3. HTTP-REST plugin: URL normalizer first, then OpenAPI parser, then FastAPI/Flask/Django detectors, then TS client detector.
4. `trace_cross_language` MCP tool (connects traversal engine to MCP).
5. Interface resource handlers.
6. `plugin_reload` MCP tool.
7. Resource subscriptions and notifications.
8. WebSocket plugin.
9. omniORB-IDL plugin.
10. Traversal integration into `find_callers` and `find_callees`.
11. `get_graph_slice` with interface edge types.
12. Backlog stubs.
13. Regression test harness.

Reasoning:

- Plugin base and registry first to establish the infrastructure every plugin uses.
- HTTP-REST before WebSocket and IDL because it has the most readily available test fixtures (any Python web framework + TypeScript client).
- `trace_cross_language` tool before the later plugins so each plugin can be exercised as it lands.
- omniORB-IDL last because it requires both Phase 5 C++ libclang and Phase 5 Python pyan3 to be stable.
- Backlog stubs last because they are no-ops.

---

## 23. Downstream Consumer Matrix

| Later phase | What it consumes from Phase 7 |
|---|---|
| Phase 8 - Repo-QA | `get_interface_contract` for `contract-check` question class; `trace_cross_language` for `behaviour-trace` question class |
| Phase 9 - Fault localisation | `trace_cross_language` for cross-language suspect expansion; interface edges in graph neighbor traversal; `exposes`/`consumes` edges in ego-graph |
| Phase 10 - Evaluation harness | SWE-PolyBench-style cross-language fixtures exercising HTTP-REST and IDL traversal |
| Phase 11 - Patch review | Interface contract compatibility check using `InterfaceRecord`; generated artifact detection blocking direct-edit recommendations; `ffi` edges for ABI/API break detection |
| Phase 12 - SAST repair | Interface node context in repair prompt; generated artifact awareness |
| Phase 13 - Bug-resolve | Cross-language suspect expansion via `trace_cross_language`; interface contract loaded for patch context |
| Phase 14 - Implementation-check | `get_interface_contract` for clause grounding at interface boundaries; `mids-valve`-style interface spec check |
| Phase 15 - Blast radius | `exposes`/`consumes`/`implements`/`ffi` edges for cross-language impact traversal; generated artifact impact notes |
| Phase 17 - Memory | Interface IDs as trajectory graph node IDs for boundary-crossing decisions |
| Phase 18 - Release gates | SWE-PolyBench-style and Defects4C-style cross-language drift evaluation |

---

## 24. Exit Criteria Mapping And Definition Of Done

### 24.1 Exit Criteria Mapping

Source Phase 7 exit criterion:

- `trace_cross_language(start_symbol)` can cross at least one plugin boundary.

Concrete acceptance:

- `trace_cross_language` with a FastAPI handler in the HTTP-REST fixture returns at least one hop to the matching TS client callsite.
- `trace_cross_language` with a Python IDL caller in the omniORB-IDL fixture returns at least one hop to the C++ servant method.

Source Phase 7 exit criterion:

- Interface contracts are available as resources.

Concrete acceptance:

- `code-intelligence://interfaces` lists the HTTP-REST and omniORB-IDL plugins.
- `code-intelligence://interfaces/http-rest/GET%20%2Fusers%2F%7Bid%7D` returns an `InterfaceRecord` for the fixture route.
- `code-intelligence://interfaces/omniorb-idl/Calculator` returns an `InterfaceRecord` for the fixture IDL interface.

Source Phase 7 exit criterion:

- Cross-repo traversal works when two registered repos are linked by an interface.

Concrete acceptance:

- Two fixture repos registered: Python server repo and TypeScript client repo.
- `trace_cross_language` from Python handler crosses HTTP boundary to TS client in the other repo.
- The hop is tagged `cross_repo=True`.

### 24.2 Definition Of Done

Phase 7 is done when:

- Plugin base interface, registry, and capability model are implemented and tested.
- `InterfaceRecord` and `InterfaceOperation` models validate against Phase 1 schemas.
- Cross-language traversal engine chains hops with cycle prevention and hop bound.
- HTTP-REST plugin produces `http_route` nodes, `exposes`, and `consumes` edges for fixture.
- WebSocket plugin produces `websocket_event` nodes, `exposes`, and `consumes` edges for fixture.
- omniORB-IDL plugin produces `idl_interface` nodes, `implements`, `consumes`, and `ffi` edges for fixture.
- Generated artifact tracking marks generated stubs as `generated=True`.
- Plugin backlog stubs are registered with `available=False`.
- `trace_cross_language` MCP tool crosses at least one plugin boundary in each fixture.
- `plugin_reload` MCP tool graduates from Phase 4 stub to working implementation.
- `code-intelligence://interfaces` and per-interface resources are readable and subscribable.
- Traversal integration: `find_callers` and `find_callees` return cross-language results with `include_cross_language=True`.
- All Phase 3/4/5/6 tests continue to pass.

---

## 25. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| omniidl not installed on developer machines | omniORB-IDL plugin unavailable; fixture tests skipped | Fallback IDL tokenizer with `heuristic` confidence; CI matrix gates IDL tests on omniidl availability; clear install docs |
| FastAPI/Flask/Django version changes break AST detection patterns | Route detection misses or over-detects | Version-pin fixture repos; test against multiple framework versions; use Semgrep rules as an augmenting fallback |
| URL normalization mismatches between server and client styles | Wrong `consumes` edges or missed links | Comprehensive URL normalizer test matrix; canonical form documented; snapshot tests for normalizer output |
| Dynamic event names in WebSocket produce too many ambiguous candidates | Traversal result overwhelmed with candidates | Default `include_ambiguous=False`; set maximum candidate count per operation; document dynamic-name limitation |
| Plugin re-index after large IDL change rebuilds entire servant link graph | `plugin_reload` is slow | Make IDL linker incremental by interface; support per-interface reload; run as task |
| Cross-repo link leaks information about unauthorized repo | Privacy violation | Authorization context check for both repos before emitting cross-repo link to client |
| Generated file detection misclassifies hand-written files | Legitimate edits blocked or warned incorrectly | Generated file detection is conservative: require both file path pattern AND file header/comment marker; allow override in plugin config |
| Multiple frameworks in same repo (Flask + FastAPI) | Duplicate route detection, conflicting records | Deduplicate by canonical path+method before emitting; pick highest-confidence source |
| TS client URL extracted from variable fails to link to server route | Missing `consumes` edges | Variable-source URL emitted as ambiguous candidate; note in traversal result and diagnostics |
| Phase 4 `plugin_reload` stub callers expect old no-op response shape | Breaking change for Phase 4 test clients | Phase 7 `plugin_reload` must be backward-compatible with the stub's output schema; new fields are additive |

---

## 26. Completion Report Template And Minimal First Slice

### 26.1 Completion Report Template

When Phase 7 implementation is complete, report:

```text
Phase 7 completion report

Implemented:
- Plugin base interface and registry:
- InterfaceRecord and operation model:
- Cross-language traversal engine:
- HTTP-REST plugin (OpenAPI + framework + TS client):
- WebSocket plugin:
- omniORB-IDL plugin:
- Plugin backlog stubs:
- trace_cross_language MCP tool:
- plugin_reload MCP tool (graduated from Phase 4 stub):
- Interface MCP resources:
- find_callers / find_callees cross-language integration:

Verification:
- Plugin base and registry tests:
- HTTP-REST plugin tests:
- WebSocket plugin tests:
- omniORB-IDL plugin tests:
- Traversal engine tests:
- MCP tool tests:
- Resource tests:
- Integration tests:
- Regression harness:
- Local verify command:

Exit criteria:
- trace_cross_language crosses HTTP-REST boundary:
- trace_cross_language crosses IDL boundary:
- Interface contracts available as resources:
- Cross-repo traversal works between two registered repos:
- Phase 3/4/5/6 tests still pass:

Known limitations:
-

Follow-up for Phase 8 (Repo-QA):
-
```

### 26.2 Minimal First Slice Within Phase 7

If Phase 7 needs to be split further, implement this first:

1. Plugin base interface, `InterfaceRecord` model, and plugin registry.
2. Cross-language traversal engine with no-op test plugin.
3. URL normalizer.
4. HTTP-REST plugin: OpenAPI parser and FastAPI detector only.
5. `trace_cross_language` MCP tool.
6. `code-intelligence://interfaces` list resource.
7. `code-intelligence://interfaces/{plugin_id}/{interface_name}` resource.
8. `plugin_reload` tool (working, for HTTP-REST plugin only).
9. HTTP-REST fixture repo with a FastAPI server and a TypeScript fetch client.
10. Integration test: `trace_cross_language` from FastAPI handler to TS fetch client.

This minimal slice validates the plugin contract, the traversal engine, the MCP exposure, and the core HTTP-REST path without requiring WebSocket or omniORB-IDL infrastructure. WebSocket and IDL plugins can follow in subsequent slices.
