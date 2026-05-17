# LLM-SCA Tooling Technology Stack

> Date: 2026-05-09
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Purpose: consolidated, authoritative technology stack reference for all implementation phases.
> All phase documents inherit their tool choices from this document. Where a phase document names a specific library, this document is the source of truth for version constraints, rationale, and integration notes.

---

## 1. Stack At A Glance

```text
Runtime          Python 3.12+, uv
API / MCP        FastAPI, FastMCP (stdio-first), uvicorn
CLI              Typer + Rich
Database         SQLite (local/dev) · PostgreSQL (production/CI)
ORM / migrations SQLModel (async) · Alembic
Graph            SQLModel (persistence) + NetworkX (in-memory traversal)
Embeddings       fastembed + sqlite-vec (dev) / pgvector (production)
Schemas          Pydantic v2 · jsonschema · jsf
HTTP client      httpx (async)
Code backends    universal-ctags · tree-sitter · pyan3 · Semgrep · Bandit
SARIF            Custom normalizer (no external library)
Testing          pytest · pytest-cov · pytest-xdist · pytest-asyncio · tox
                 unittest · unittest.mock
Code quality     ruff · isort · black · mypy · import-linter · bandit
Security         detect-secrets · pip-audit · Semgrep
Parsers          orjson · ruamel.yaml · lxml · defusedxml · selectolax · markdown-it-py
Pre-commit       pre-commit
```

---

## 2. Runtime And Packaging

### 2.1 Python

- Minimum version: **Python 3.12**.
- Type hints required on all function signatures and class attributes (PEP 484).
- f-strings preferred over `.format()` or `%` formatting.
- `pathlib.Path` preferred over `os.path`.

### 2.2 uv

- All Python commands use `uv run <command>`.
- Dependencies pinned via `uv.lock`.
- Dev and prod dependencies separated in `pyproject.toml` under `[tool.uv]` `dev-dependencies`.
- `uv lock --upgrade` is a dependency-update event and requires a full verify pass before merge.
- The `uv.lock` file is committed to the repository and is part of supply-chain evidence.

---

## 3. Code Quality

### 3.1 Formatting

Run in this order:

```bash
uv run isort .
uv run black .
uv run ruff check . --fix
```

- `isort`: import sorting. Configuration in `pyproject.toml` under `[tool.isort]`.
- `black`: code formatting. Line length 88 (black default). Configuration in `pyproject.toml` under `[tool.black]`.
- `ruff`: linting only; **ruff's formatter is disabled**. Black owns all formatting decisions.

`pyproject.toml` excerpt:

```toml
[tool.isort]
profile = "black"
line_length = 88

[tool.black]
line-length = 88
target-version = ["py312"]

[tool.ruff]
line-length = 88
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "T20"]
```

### 3.2 Type Checking

- **mypy** with the `pydantic-mypy` plugin for Pydantic v2 model type inference.
- Run: `uv run mypy src/`.
- `mypy.ini` or `pyproject.toml` `[tool.mypy]` section must include:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["networkx.*", "tree_sitter.*", "pyan.*"]
ignore_missing_stubs = true
```

### 3.3 Import Architecture Enforcement

**import-linter** enforces the architectural module layering. No phase may import from a higher-level layer without explicit declaration.

Layering contract (bottom to top; each layer may import from layers below it):

```text
errors
config
schemas
telemetry
governance     (may import: errors, config, schemas)
operations     (may import: errors, config, schemas, telemetry, governance)
graph          (may import: errors, config, schemas)
indexing       (may import: errors, config, schemas, graph)
sarif          (may import: errors, config, schemas, graph)
plugins        (may import: errors, config, schemas, graph, sarif)
mcp_server     (may import: all below + operations, governance)
workflows      (may import: all below + mcp_server)
evaluation     (may import: all below + workflows)
memory         (may import: all below + evaluation)
harness        (may import: all below)
cli            (may import: all — top of the stack)
```

`.importlinter` configuration:

```ini
[importlinter]
root_packages = llm_sca_tooling

[importlinter:contract:layered-architecture]
name = Layered architecture
type = layers
layers =
    llm_sca_tooling.cli
    llm_sca_tooling.harness
    llm_sca_tooling.memory
    llm_sca_tooling.evaluation
    llm_sca_tooling.workflows
    llm_sca_tooling.mcp_server
    llm_sca_tooling.plugins
    llm_sca_tooling.sarif
    llm_sca_tooling.indexing
    llm_sca_tooling.graph
    llm_sca_tooling.operations
    llm_sca_tooling.governance
    llm_sca_tooling.telemetry
    llm_sca_tooling.schemas
    llm_sca_tooling.config
    llm_sca_tooling.errors
```

Run: `uv run lint-imports`.

### 3.4 Python SAST (Bandit)

**Bandit** analyses Python AST for security anti-patterns in source code. It belongs in the code quality pipeline because it catches issues at the same level as ruff or mypy — in the code you write — rather than scanning for leaked credentials or vulnerable dependencies.

Catches: hardcoded passwords, subprocess injection, unsafe `assert` in security paths, unsafe deserialization, weak cryptography, SQL injection patterns, and more.

Run: `uv run bandit -r src/ -c pyproject.toml`.

```toml
[tool.bandit]
exclude_dirs = ["tests"]
skips = []
```

Bandit runs in the verify pipeline alongside ruff and mypy. A high-severity finding blocks the verify command; medium-severity findings produce warnings.

---

## 4. Security Scanning And Compliance

### 4.1 Semgrep

Predicate-driven static analysis. Required for:

- **Phase 6**: SARIF production alongside Bandit.
- **Phase 7**: HTTP route and WebSocket event detection in the HTTP-REST and WebSocket interface plugins.
- **Phase 12**: Predicate negation on clean corpus for SAST repair examples.

Semgrep is invoked as a subprocess tool (not a Python library import). Its output is consumed as SARIF v2.1.0.

### 4.2 detect-secrets

Secrets baseline scanning. Integrated into pre-commit. A `.secrets.baseline` file is committed to the repository.

Run: `detect-secrets scan --baseline .secrets.baseline`.

HC1 enforcement: any commit that introduces a new secret pattern must fail the pre-commit hook.

### 4.3 pip-audit

Dependency vulnerability auditing against PyPI advisory database.

Run: `uv run pip-audit`.

CI gate: `pip-audit` runs in CI on every pull request. A known vulnerability with a fix available fails the gate.

### 4.4 Pre-Commit

Pre-commit framework manages all git hook-based checks. Listed as a dev dependency in `pyproject.toml`.

`.pre-commit-config.yaml` minimum hooks:

```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
```

---

## 5. Testing

### 5.1 Test Framework Stack

| Tool | Role |
|---|---|
| `unittest` + `unittest.mock` | Base test case class and mock/patch utilities (stdlib) |
| `pytest` | Test runner; discovers and runs both `unittest.TestCase` and pytest-style `def test_` functions |
| `pytest-cov` | Coverage measurement |
| `pytest-xdist` | Parallel test execution (`-n auto`) |
| `pytest-asyncio` | Async test support (`asyncio_mode = "auto"`) |
| `tox` | Multi-Python-version matrix (3.12, 3.13) |

`pyproject.toml` excerpt:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--tb=short -q"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

Convention: write **pytest-style** tests by default (`def test_` or `async def test_`). Reserve `unittest.TestCase` subclasses only when test lifecycle methods (`setUp`/`tearDown`) are necessary. Use `unittest.mock.patch` and `unittest.mock.MagicMock` for mocking in both styles.

### 5.2 Async Test Convention

All tests that exercise async code must be `async def`. With `asyncio_mode = "auto"`, no decorator is needed:

```python
async def test_run_record_create() -> None:
    writer = RunRecordWriter(...)
    run_id = await writer.create_run(...)
    assert run_id.startswith("run:")
```

### 5.3 JSON Schema Test Fixtures

**jsonschema** validates exported `.schema.json` files against real payloads in tests.

**jsf** (Python json-schema-faker: `pip install jsf`) generates valid and invalid fixture payloads from JSON Schema definitions. Used in Phase 1 to produce positive and negative test cases without hand-writing every fixture.

```python
from jsf import JSF

faker = JSF.from_file("schemas/graph.schema.json")
valid_node = faker.generate()   # always valid against the schema
```

For invalid fixtures, modify generated objects by removing required fields or injecting wrong types.

If `jsf` proves insufficient for complex `$ref` schemas, fall back to `hypothesis` + `hypothesis-jsonschema` for property-based generation.

### 5.4 Coverage Targets By Module

| Module | Target |
|---|---|
| `errors`, `config` | ≥ 95% |
| `schemas`, `telemetry`, `operations` | ≥ 95% |
| `governance`, `graph`, `sarif` | ≥ 90% |
| `plugins`, `harness`, `indexing` | ≥ 90% |
| `mcp_server`, `workflows` | ≥ 85% |
| `cli`, `evaluation`, `memory` | ≥ 85% |

---

## 6. Data And Configuration Layer

### 6.1 Pydantic v2

All data models use Pydantic v2. Key conventions:

- `model_config = ConfigDict(extra="forbid")` on stable contract objects.
- UTC datetimes as `datetime` fields with `AwareDatetime` annotation or serialized as ISO-8601 strings.
- POSIX-normalized relative paths as `str` (not `Path`) in persisted models to ensure JSON-safe serialization.
- `model_json_schema()` for JSON Schema export — do not hand-write `.schema.json` files.
- Lowercase string enum values as `StrEnum` or `Literal` unions.

### 6.2 jsonschema

Validates raw JSON payloads against the exported `.schema.json` files. Used in:

- Phase 1 round-trip tests.
- MCP server input validation for clients that submit raw JSON rather than going through Python models.
- Cross-language contract testing (a JS or C++ client can validate its output against the same schema files).

```python
import jsonschema, json, pathlib

schema = json.loads(pathlib.Path("schemas/graph.schema.json").read_text())
jsonschema.validate(instance=payload, schema=schema)
```

### 6.3 jsf

Generates valid fixture payloads from JSON Schema. Used in Phase 1 test fixtures.

---

## 7. Database And ORM Layer

### 7.1 SQLModel

SQLModel = Pydantic v2 + SQLAlchemy 2.0. Provides:

- Pydantic-validated table models.
- Async session via `AsyncSession`.
- Compatible with both SQLite (dev) and PostgreSQL (production).

Async drivers:

| Database | Async driver |
|---|---|
| SQLite | `aiosqlite` |
| PostgreSQL | `asyncpg` |

Connection string convention:

```python
# SQLite (dev)
DATABASE_URL = "sqlite+aiosqlite:///./llm_sca_tooling.db"

# PostgreSQL (production)
DATABASE_URL = "postgresql+asyncpg://user:password@host/dbname"
```

Sensitive credentials must never appear in source code, logs, or committed config files. Use environment variables (`LLM_SCA_DATABASE_URL`) and the HC1 constraint.

### 7.2 Alembic

Database migration tool for SQLModel/SQLAlchemy schema evolution.

- Migration scripts live in `alembic/versions/`.
- `alembic upgrade head` applies all pending migrations.
- `alembic revision --autogenerate -m "description"` generates a migration from model diffs.
- Every phase that changes a SQLModel table model must include an Alembic migration script.
- SQLite note: Alembic's `batch_alter_table` context is required for column changes on SQLite (SQLite does not support `ALTER COLUMN` natively).

`alembic.ini` and `alembic/env.py` are created in Phase 2 when the first SQLModel tables are defined.

---

## 8. Graph Layer

### 8.1 Design: SQL For Persistence, NetworkX For Traversal

Graph nodes and edges are persisted in SQLModel tables. In-memory traversal (ego graphs, multi-hop paths, slices, callers/callees) is performed by loading a subgraph into **NetworkX** and running graph algorithms there.

```text
SQLModel tables          NetworkX DiGraph (in-memory subgraph)
GraphNode, GraphEdge  →  load_subgraph(node_ids) → nx.DiGraph
                         nx.ego_graph(), nx.shortest_path(), ...
```

Cache policy: subgraphs are cached in memory keyed by `(repo_id, git_sha, frozenset(seed_node_ids))`. Cache is invalidated on `graph_update` events.

### 8.2 NetworkX Conventions

- Use `nx.DiGraph` (directed graph) as the default type. Use `nx.MultiDiGraph` only when multiple parallel edges between two nodes are required (e.g. multiple call sites between the same pair of functions).
- Store the full `GraphNode` and `GraphEdge` Pydantic models as node/edge attributes.
- Graph traversal functions live in `llm_sca_tooling.graph.traversal` and must not import from `mcp_server`, `workflows`, or higher layers (enforced by import-linter).

---

## 9. Embeddings And Vector Search

### 9.1 Local Stack: fastembed + sqlite-vec

**fastembed** generates embeddings locally without an external API:

- Default model: `BAAI/bge-small-en-v1.5` (fast, small footprint).
- Embeddings are cached per symbol keyed by `(repo_id, symbol_path, git_sha)`.
- Cache is invalidated when the owning file changes.

**sqlite-vec** adds vector search to SQLite via a loadable extension. Returns approximate nearest neighbours using cosine similarity.

### 9.2 Production Stack: pgvector

When PostgreSQL is the backend, use the `pgvector` extension. The embedding cache table schema must be compatible with both backends — abstract the vector column type behind a thin storage interface so the switch requires only a configuration change.

### 9.3 Phase Introduction

The embeddings layer is introduced in **Phase 9** (fault localisation). Phases 0–8 must not depend on `fastembed` or `sqlite-vec`. A stub interface is defined in Phase 0; the implementation follows in Phase 9.

---

## 10. API And MCP Layer

### 10.1 FastAPI

Async-native API framework. Used as the HTTP server for the MCP Streamable HTTP transport (Phase 19) and any future REST endpoints.

All FastAPI route handlers are `async def`. Dependency injection via `Depends()` is used for database sessions, config, and the policy evaluator.

### 10.2 FastMCP

FastMCP is the MCP server framework. It provides resource, tool, and prompt registration with decorators and automatic MCP protocol compliance.

Transport plan:

| Phase | Transport | Rationale |
|---|---|---|
| Phase 4 | stdio | Default for local IDE and Claude Code integration |
| Phase 19 | stdio + Streamable HTTP | Multi-client and remote deployment |

FastMCP server entry point pattern:

```python
from fastmcp import FastMCP

mcp = FastMCP("code-intelligence")

@mcp.resource("code-intelligence://repos")
async def list_repos() -> list[dict]: ...

@mcp.tool()
async def graph_build(repo_path: str) -> dict: ...
```

### 10.3 uvicorn

ASGI server for running FastAPI when HTTP transport is needed. Listed as a production dependency from Phase 4 onward. Not required for stdio-only deployments but included in `pyproject.toml` from Phase 0 to keep the dependency set stable.

---

## 11. CLI Layer

### 11.1 Typer

CLI framework built on Click, using Python type hints for argument and option definitions.

```python
import typer
app = typer.Typer()

@app.command()
def version() -> None:
    typer.echo(f"llm-sca-tooling {__version__}")
```

### 11.2 Rich

Terminal output formatting. Rich is used for:

- Structured tables (harness status, eval reports, run record summaries).
- Progress bars (graph build, indexing runs).
- Formatted panels (verdict output, incident summaries).
- Syntax-highlighted code snippets in CLI output.

**Critical integration note — RichHandler**: Rich and the standard `logging` module must be wired together through `RichHandler`. Without this, log output and Rich-rendered output will interleave and corrupt each other in the terminal.

Correct logging setup in the CLI entry point:

```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
```

**Non-TTY context**: In CI and piped output, Rich must detect a non-interactive terminal and disable colour and markup automatically. Use `Console(force_terminal=False)` or check `sys.stdout.isatty()` before enabling Rich formatting.

**Scope constraint**: Rich imports and `Console` usage are restricted to the `cli` layer only. Other modules must not import `rich` directly (enforced by import-linter). Pass pre-rendered strings or structured data up to the CLI layer for display.

---

## 12. HTTP Client

### 12.1 httpx

Async HTTP client. Used in:

- **Phase 7**: HTTP-REST interface plugin (fetching OpenAPI documents, probing routes).
- **Tests**: `httpx.AsyncClient` as the FastAPI test client.

**Network policy**: all outbound HTTP calls must pass through an allowlist check before the request is dispatched (HC5 enforcement). The httpx client should be wrapped in a `PolicyAwareHTTPClient` that validates the target URL against the governance policy.

---

## 13. Code Intelligence Backends (Subprocess Tools)

### 13.1 Critical Architecture Boundary: Blocking Subprocess Calls In Async Code

These tools are invoked as external processes, not imported as Python libraries. Their output is parsed and normalised into the common graph schema.

**Subprocess calls block the asyncio event loop** if invoked with the standard `subprocess` module in async code paths. They must always be called via `asyncio.create_subprocess_exec` (for fire-and-collect patterns) or wrapped in `loop.run_in_executor` for synchronous APIs.

The exception is `pyan3`, which is a Python library API (not a subprocess call) and must be wrapped in a thread pool executor to avoid blocking the event loop on CPU-bound analysis.

This boundary applies to every phase that shells out to an indexing or analysis tool.

### 13.2 Backend Inventory

| Tool | Purpose | Phase introduced | Output format |
|---|---|---|---|
| `universal-ctags` | Symbol definitions (functions, classes, methods, variables) for all languages | Phase 3 | JSON (`--output-format=json`) |
| `tree-sitter` + grammars | AST nodes and syntax facts | Phase 3 | Python binding (not subprocess) |
| `pyan3` | Python call and import graph | Phase 3 | Python API (run in thread pool) |
| `semgrep` | Predicate-driven SAST, HTTP route detection, SARIF production | Phase 6 | SARIF v2.1.0 via `--sarif` |
| `bandit` | Python AST security linting | Phase 6 | SARIF via `-f sarif` |

Tree-sitter Python package and language grammars:

```text
tree-sitter            core Python binding
tree-sitter-python     Python grammar
tree-sitter-javascript JavaScript grammar (covers TypeScript)
tree-sitter-c          C grammar
tree-sitter-cpp        C++ grammar
```

### 13.3 Backend Availability And Degradation

Backends are capability-checked at startup. Missing backends degrade the graph to partial evidence rather than failing the whole index. The `graph_build` run record must include backend availability in its run events.

---

## 14. SARIF Layer

### 14.1 Custom Normalizer

No external SARIF parsing library is used. The custom normalizer is implemented in `llm_sca_tooling.sarif` against the SARIF v2.1.0 JSON schema specification.

Rationale: available Python SARIF libraries are poorly maintained and do not cover the full v2.1.0 schema. A custom normalizer can be kept thin, tested against real analyser output, and evolved with the project.

The normalizer must:

- Parse SARIF v2.1.0 JSON documents.
- Extract runs, results, rules, locations, logical locations, code flows, and tool information.
- Normalise rule severity across analysers (Semgrep, Bandit, CodeQL, external).
- Extract predicate IDs where the analyser exposes them (CodeQL query IDs, Semgrep rule IDs).
- Bind alerts to file paths and line spans.
- Emit `SarifResult` Pydantic models that feed `warned_by` graph edges.
- Validate input using `jsonschema` loaded from the official SARIF v2.1.0 schema.

The official SARIF v2.1.0 JSON Schema is committed to `schemas/sarif-schema-2.1.0.json` and used for input validation only — it is not generated from Python models.

### 14.2 SARIF Delta Utility

The SARIF delta utility compares two SARIF runs and classifies each result as `appeared`, `disappeared`, `unchanged`, or `changed_severity`. Used in Phase 6 for patch-risk classification and Phase 12 for SAST repair verification.

---

## 15. Async Conventions

The entire application stack is asyncio-native. Follow these conventions in every module:

| Rule | Detail |
|---|---|
| `async def` for all I/O | Database queries, HTTP calls, subprocess wrappers, file reads in hot paths |
| No blocking subprocess in async | Use `asyncio.create_subprocess_exec` for subprocess calls; never `subprocess.run` in async paths |
| No `time.sleep` in async code | Use `asyncio.sleep` |
| Thread pool for CPU-bound code | Use `loop.run_in_executor` for `pyan3`, tree-sitter parsing, heavy JSON serialization |
| Session-per-request for DB | Create `AsyncSession` via `async with AsyncSession(engine) as session:` |
| No global mutable state | Pass session and config via function arguments or `contextvars.ContextVar` |
| `anyio.run_process` in tests | Use for subprocess calls in tests to stay backend-agnostic |

---

## 16. pyproject.toml Dependency Reference

### 16.1 Production Dependencies

```toml
[project]
name = "llm-sca-tooling"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # core
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    # CLI
    "typer>=0.12",
    "rich>=13.0",
    # API + MCP
    "fastapi>=0.115",
    "fastmcp>=2.0",
    "uvicorn[standard]>=0.30",
    # database
    "sqlmodel>=0.0.21",
    "alembic>=1.13",
    "aiosqlite>=0.20",
    "asyncpg>=0.29",
    "sqlite-vec>=0.1",
    # graph
    "networkx>=3.3",
    # embeddings (introduced Phase 9; uncomment then)
    # "fastembed>=0.3",
    # HTTP client
    "httpx>=0.27",
    # JSON Schema validation
    "jsonschema>=4.23",
    # code intelligence backends (Python bindings only)
    "tree-sitter>=0.22",
    "tree-sitter-python>=0.22",
    "tree-sitter-javascript>=0.22",
    "tree-sitter-c>=0.22",
    "tree-sitter-cpp>=0.22",
    "pyan3>=1.4",
    # document format parsers
    "orjson>=3.10",
    "ruamel.yaml>=0.18",
    "tomli-w>=1.1",
    "lxml>=5.2",
    "defusedxml>=0.7",
    "selectolax>=0.3",
    "markdown-it-py>=3.0",
]
```

### 16.2 Development Dependencies

```toml
[tool.uv]
dev-dependencies = [
    # testing
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-xdist>=3.5",
    "pytest-asyncio>=0.23",
    "tox>=4.0",
    "anyio[trio]>=4.0",
    # JSON Schema fixtures
    "jsf>=0.11",
    # code quality
    "mypy>=1.10",
    "pydantic-mypy>=2.0",
    "ruff>=0.4",
    "isort>=5.13",
    "black>=24.0",
    "import-linter>=2.1",
    # security
    "bandit[toml]>=1.7",
    "detect-secrets>=1.5",
    "pip-audit>=2.7",
    # pre-commit
    "pre-commit>=3.7",
    # type stubs
    "types-jsonschema",
    "networkx-stubs",
    "lxml-stubs>=0.5",
    "types-defusedxml",
]
```

### 16.3 Phase-By-Phase Dependency Introduction

| Phase | New dependencies introduced |
|---|---|
| H0 | `pre-commit`, `detect-secrets`, `bandit`, `pip-audit` (dev tools active) |
| 0 | All production deps except `fastembed` (including all document parsers); all dev deps listed above |
| 1 | `jsonschema`, `jsf` already listed; activate in Phase 1 tests |
| 2 | `alembic`, `aiosqlite`, `asyncpg`, `sqlite-vec` (activate) |
| 3 | `tree-sitter` + grammars, `pyan3` (activate) |
| 4 | `fastmcp`, `uvicorn` (activate MCP server) |
| 5 | Additional tree-sitter language grammar packages |
| 6 | `semgrep` (subprocess binary; no Python dep entry needed) |
| 7 | `httpx` (activate HTTP-REST plugin) |
| 9 | `fastembed` (uncomment in `pyproject.toml`) |

---

## 17. Subprocess Tool Installation Policy

Subprocess tools (`universal-ctags`, `semgrep`) are not Python package dependencies. They must be installed separately and their versions recorded in:

1. The supply-chain ledger (Phase H0).
2. The Harness Condition Sheet for any run that uses them.
3. The CI environment setup script or devcontainer definition.

CI must install these tools before running tests or eval suites that depend on them. Missing tools must produce backend-unavailable warnings in the graph build run record, not unhandled exceptions.

---

## 18. Architectural Constraints Summary

The following constraints are enforced by `import-linter`, `mypy --strict`, and CI:

| Constraint | Detail |
|---|---|
| No upward layer imports | `graph` must not import from `workflows`; enforced by `.importlinter` |
| No blocking subprocess in async | Use async subprocess wrappers; never `subprocess.run` in async paths |
| No `print()` in production code | Use `logging` with `RichHandler` in CLI; structured logging elsewhere |
| No hard-coded credentials | All sensitive config via environment variables |
| `extra="forbid"` on stable models | Pydantic contract objects reject unknown fields |
| No hand-written `.schema.json` | Always generate from `model_json_schema()` |
| No `fastembed` before Phase 9 | Commented in `pyproject.toml` until Phase 9 |
| SARIF parsing in `sarif` module only | No direct SARIF JSON parsing in other modules |
| Rich imports in `cli` layer only | Other modules must not import `rich` directly |
| `RichHandler` wired before first log | Set up in CLI entry point before any module logs |

---

---

## 20. Document Format Parsers

### 20.1 Design Principle

Every parser choice prioritises three properties in order: **security** (no untrusted input leads to RCE or DoS), **maintenance** (actively developed as of 2026), and **performance** (fastest library at the tier). The stdlib is preferred when it is sufficient; a Rust/C-backed library is chosen when the format is performance-critical or security-hardened handling is required.

### 20.2 JSON — orjson

**orjson** (PyPI: `orjson`) is the Rust-backed JSON library. It is the primary JSON serialiser/deserialiser for:

- SARIF files (can be hundreds of MB from CodeQL runs).
- Run records and session trace JSONL.
- Graph schema exports and MCP resource payloads.

Key properties:

- 10–100x faster than stdlib `json` on large documents.
- Native support for `datetime`, `UUID`, and dataclasses without custom encoders.
- Pydantic v2 has native orjson support: `model.model_dump_json()` uses orjson internally when available.
- Returns `bytes`, not `str` — callers that need `str` call `.decode()`.

The stdlib `json` module remains acceptable for small config payloads where performance is irrelevant.

### 20.3 YAML — ruamel.yaml

**ruamel.yaml** (PyPI: `ruamel.yaml`) is the YAML parser. It is used for:

- Reading and writing `AGENTS.md` YAML frontmatter.
- Parsing CI workflow files (`.github/workflows/*.yml`).
- Reading and writing Harness Condition Sheet YAML files.
- Any config file where comments and formatting must be preserved on round-trips.

Key properties:

- Implements YAML 1.2 (PyYAML implements only YAML 1.1, which has footgun behaviours such as bare `yes`/`no` parsed as booleans).
- Round-trip preserving: editing a YAML file programmatically does not destroy comments or formatting.
- **Always use** `YAML(typ='safe')` for untrusted input. Never use `yaml.load()` or `YAML(typ='unsafe')` with untrusted data.

### 20.4 TOML — stdlib tomllib + tomli-w

For reading TOML, use the **stdlib `tomllib`** module (Python 3.11+, no install required).

For writing TOML, use **tomli-w** (PyPI: `tomli-w`), the minimal write-only companion.

Use cases:

- Reading `pyproject.toml` programmatically (tool version reporting, config discovery).
- Writing generated TOML config files.

If round-trip preservation with comment retention is needed (e.g. programmatically editing `pyproject.toml`), use **tomlkit** (PyPI: `tomlkit`) instead.

### 20.5 XML — lxml + defusedxml

**lxml** (PyPI: `lxml`) is the XML parser. It wraps libxml2/libxslt, supports XPath, XSLT, and schema validation, and is 2–3x faster than stdlib `xml.etree.ElementTree`.

**defusedxml** (PyPI: `defusedxml`) is required for all XML parsing from untrusted sources.

Security rule: **all stdlib XML parsers** (`xml.etree`, `xml.dom`, `xml.sax`, `xml.parsers.expat`) are vulnerable to XXE (XML External Entity injection), Billion Laughs DoS, and quadratic blowup attacks when processing untrusted input. In this project, untrusted XML sources include repository build files, issue attachments, and any external tool output.

Hardened lxml parser configuration for untrusted sources:

```python
from lxml import etree

safe_parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    forbid_entities=True,
    forbid_dtd=True,
)
tree = etree.fromstring(untrusted_xml_bytes, parser=safe_parser)
```

For trusted, internal XML (e.g. generated tool output), plain lxml without the restrictions is acceptable.

Use cases: build file parsing (Maven POM, Ant build.xml), any XML-format code analysis tool output.

### 20.6 HTML — lxml.html + selectolax

**lxml.html** (`lxml` already in the stack) handles structural HTML parsing with XPath and CSS selector support. Use it for spec documents and API documentation where the HTML structure is known and predictable.

**selectolax** (PyPI: `selectolax`) is the high-throughput choice when performance matters. It wraps the Lexbor C HTML5 engine, delivers 5–30x speedups over BeautifulSoup, follows the HTML5 spec for malformed markup, and is actively maintained (May 2026).

Use cases:

- Phase 14 spec ingestion: HTML documentation pages for implementation-check clause extraction.
- Phase 7 HTTP-REST plugin: OpenAPI/Swagger HTML documentation discovery.

Apply the same untrusted-input caution to HTML as to XML — use lxml's safe parser or selectolax's `HTMLParser` rather than passing untrusted HTML to a JavaScript engine or `eval`-style renderer.

### 20.7 Markdown — markdown-it-py

**markdown-it-py** (PyPI: `markdown-it-py`) is the Markdown parser. It is:

- 100% CommonMark compliant.
- A Python port of the widely trusted `markdown-it` JavaScript library.
- Used by Rich internally and by MkDocs and Jupyter.
- Actively maintained (v4.2.0, May 2026).

Use cases:

- Phase 14 spec ingestion: `AGENTS.md`, design documents, and architecture notes parsed to extract clause text for implementation-check.
- Harness Condition Sheet rendering.
- Operational review and incident report rendering.

Optional: `mdit-py-plugins` (PyPI: `mdit-py-plugins`) adds footnotes, tasklists, front-matter, and other CommonMark extensions.

### 20.8 Format Coverage Summary

| Format | Library | PyPI package | Notes |
|---|---|---|---|
| JSON | orjson | `orjson` | Primary JSON I/O; stdlib `json` for trivial payloads |
| YAML | ruamel.yaml | `ruamel.yaml` | Always use safe mode for untrusted input |
| TOML (read) | stdlib tomllib | built-in | Python 3.12+ |
| TOML (write) | tomli-w | `tomli-w` | |
| XML | lxml + defusedxml | `lxml`, `defusedxml` | defusedxml required for untrusted sources |
| HTML | lxml.html / selectolax | `lxml`, `selectolax` | selectolax for throughput; lxml for XPath |
| Markdown | markdown-it-py | `markdown-it-py` | CommonMark; optional `mdit-py-plugins` |
| INI / Config | stdlib configparser | built-in | Sufficient for `.ini`, `.cfg` |
| CSV | stdlib csv | built-in | Sufficient for tabular data |

## 19. Open Decisions And Future Choices

| Decision | Current state | When to decide |
|---|---|---|
| CodeQL adapter | Optional per architecture; not in initial stack | Phase 6 if CodeQL available |
| pgvector production setup | Deferred; `sqlite-vec` sufficient for Phase 9 | Phase 18 production hardening |
| `anyio` vs `asyncio` directly | `asyncio` directly; FastAPI uses `anyio` internally | Revisit if backend-agnostic tests become necessary |
| License scanning (`pip-licenses`) | Not in initial stack | Add in Phase H0 refresh if licence compliance required |
| `polyfactory` for Pydantic fixtures | `jsf` chosen; add if `jsf` gaps emerge | Phase 1 implementation |
| `hypothesis` + `hypothesis-jsonschema` | Fallback if `jsf` proves insufficient | Phase 1 implementation |
