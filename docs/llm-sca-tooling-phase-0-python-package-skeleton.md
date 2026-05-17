# LLM-SCA Tooling Phase 0 Implementation Plan: Python Package Skeleton

> Date: 2026-05-09
> Source plan: `llm-sca-tooling-implementation-plan.md`
> Source architecture: `llm-sca-tooling-architecture.md`
> Technology stack: `llm-sca-tooling-tech-stack.md`
> Phase: Phase 0 - Python Package Skeleton
> Primary objective: establish a maintainable Python project foundation — package scaffold, dependency management, test runner, local verify entrypoint, CI baseline, configuration model, structured logging and error model, skeleton modules, and CLI/MCP entrypoints — before any product logic is implemented.

---

## 1. Phase Summary

Phase 0 creates the Python project foundation for the LLM-SCA tooling package. It does not implement product features. It establishes the package layout, dependency management, test infrastructure, logging conventions, and skeleton modules that every later phase builds on.

The central rule for this phase is:

```text
No product logic, schema, graph, MCP server, or workflow may be implemented until the
package scaffold is in place, the test runner passes, and the local verify command runs
cleanly on an unmodified checkout.
```

Phase 0 must preserve these principles from the source plan:

- Typed Python throughout. Every function signature and class attribute must carry type hints (PEP 484).
- The package installs with a single command and produces a working CLI.
- The test suite, lint, type check, and verify path must all run before the first product commit.
- Configuration is explicit, not implicit. No hard-coded paths, endpoints, or credentials.
- Logging uses the standard `logging` module with structured, contextual messages. No `print()`.
- Skeleton modules must be real packages (importable, testable), not empty stub files.

Phase 0 depends on Phase H0 for governance manifests, permission profiles, and verify-command definitions. Phase 1 depends on Phase 0 for the package layout and test runner.

### Architecture Coverage

Phase 0 covers:

- Python package scaffold
- Module namespace and initial module layout
- Dependency management
- Test runner and lint/type-check setup
- Local verify entrypoint (delegating to Phase H0 manifest)
- Initial CI workflow
- Configuration model
- Logging and structured error model
- Session telemetry skeleton and trace writer
- Run-record writer skeleton
- Policy evaluator skeleton
- Budget monitor skeleton
- Initial CLI entrypoint
- Placeholder MCP server entrypoint
- Plugin registry skeleton
- Permission/profile configuration skeleton
- Basic fixture repositories for tests

### Inherited Paper Anchors

Use these anchors in issues, ADRs, and PR descriptions derived from Phase 0:

- `survey-yang-2025`
- `survey-issue-resolution-2026`
- `agentless`

## Technology Stack

This phase installs and configures the full production and development dependency set from `llm-sca-tooling-tech-stack.md`. Later phases activate individual libraries as their features are built; Phase 0 registers all of them in `pyproject.toml` so the dependency graph is stable from the start.

| Library / Tool | PyPI package | Version | Role in this phase |
|---|---|---|---|
| Pydantic v2 | `pydantic`, `pydantic-settings` | >=2.0 | Configuration model and all skeleton interfaces |
| Typer | `typer` | >=0.12 | CLI framework; type-hint-driven commands |
| Rich | `rich` | >=13.0 | Terminal output; `RichHandler` wired in CLI entry point before first log |
| FastMCP | `fastmcp` | >=2.0 | Placeholder MCP server entry point |
| FastAPI | `fastapi` | >=0.115 | Async HTTP server (activated Phase 4) |
| uvicorn | `uvicorn[standard]` | >=0.30 | ASGI server |
| SQLModel | `sqlmodel` | >=0.0.21 | ORM skeleton; tables added Phase 2 |
| Alembic | `alembic` | >=1.13 | Migration tool; `alembic/` directory created Phase 2 |
| aiosqlite | `aiosqlite` | >=0.20 | Async SQLite driver |
| asyncpg | `asyncpg` | >=0.29 | Async PostgreSQL driver |
| sqlite-vec | `sqlite-vec` | >=0.1 | Vector search extension (uncommented Phase 9) |
| NetworkX | `networkx` | >=3.3 | In-memory graph traversal skeleton |
| httpx | `httpx` | >=0.27 | Async HTTP client (activated Phase 7) |
| jsonschema | `jsonschema` | >=4.23 | JSON Schema validation |
| tree-sitter | `tree-sitter` + grammars | >=0.22 | AST parsing backends (activated Phase 3) |
| pyan3 | `pyan3` | >=1.4 | Python call graph (activated Phase 3) |
| orjson | `orjson` | >=3.10 | Primary JSON I/O throughout all phases |
| ruamel.yaml | `ruamel.yaml` | >=0.18 | YAML 1.2 with round-trip support |
| lxml + defusedxml | `lxml`, `defusedxml` | >=5.2 / >=0.7 | XML parsing; defusedxml required for untrusted sources |
| selectolax | `selectolax` | >=0.3 | High-throughput HTML5 parsing (Lexbor engine) |
| markdown-it-py | `markdown-it-py` | >=3.0 | CommonMark Markdown parsing (activated Phase 14) |
| fastembed | `fastembed` | >=0.3 | Local embeddings — **commented out until Phase 9** |

### Integration Notes

- `fastembed` is the only production dependency commented out at Phase 0. It is uncommented in `pyproject.toml` when Phase 9 (fault localisation) begins.
- Rich is restricted to the `cli` layer only. Other modules must not import `rich` directly — enforced by `import-linter`.
- `RichHandler` must be configured in `llm_sca_tooling.cli.main` before any module logs output, to prevent log/Rich output interleaving.
- The run-record writer skeleton (`llm_sca_tooling.operations.run_records`) uses `orjson` for JSONL output even in Phase 0. Stdlib `json` is not used in production code.
- All database access uses `AsyncSession` from SQLModel. `AsyncSession(engine)` is always used via `async with` context manager.


---

## 2. Inputs, Outputs, And Boundaries

### Required Inputs

Phase 0 depends on Phase H0 having produced or planned:

- `AGENTS.md` with HC1–HC6 and the verify-before-commit list.
- A harness-stage assessment record.
- An initial AI-readiness report.
- A verify command definition (`make verify` or equivalent).
- A `.pre-commit-config.yaml`.

Phase 0 also requires decisions on:

- Package name (recommended: `llm_sca_tooling`).
- Python version floor (required: Python 3.12+, per global preferences).
- Dependency manager (recommended: `uv`, per global preferences; `uv.lock` managed by `uv`).
- Primary test framework (required: `pytest` per global preferences; `tox` for multi-version).

### Phase Outputs

Phase 0 should produce:

- **Installable package**: `uv install` or `pip install -e .` produces a working package.
- **CLI entrypoint**: `llm-sca-tooling --version` and `llm-sca-tooling config` work.
- **Placeholder MCP server**: the server starts in development mode and logs its startup.
- **Skeleton modules**: all key module namespaces are importable and documented with their intended purpose.
- **Test suite**: `uv run pytest tests/` runs and passes.
- **Verify command**: `make verify` (or equivalent) runs lint, type check, tests, secrets scan, and dependency scan.
- **CI workflow**: `.github/workflows/ci.yml` runs on pull requests and main-branch pushes.
- **Configuration model**: `llm_sca_tooling.config` can load and validate a configuration file.
- **Logging model**: `llm_sca_tooling.telemetry` exposes a structured logger and trace-writer skeleton.
- **Run-record writer skeleton**: `llm_sca_tooling.operations` can create a run record, append an event, and close it.
- **Policy evaluator skeleton**: `llm_sca_tooling.governance` can evaluate a tool-call event against a stub policy.
- **Budget monitor skeleton**: `llm_sca_tooling.operations` can check a token count against a budget limit.
- **Plugin registry skeleton**: `llm_sca_tooling.plugins` can register and load a no-op plugin.
- **Permission profile skeleton**: `llm_sca_tooling.governance` can load a permission profile and return an allow/deny decision.
- **Fixture repositories**: small test fixture repositories for use in later phase tests.

### Non-Goals

Do not implement these in Phase 0:

- Graph schemas or typed evidence models (Phase 1).
- Graph storage or repository registry (Phase 2).
- Repository indexing or language backends (Phase 3).
- Full MCP resources, tools, or task handling (Phase 4).
- Full operational harness tools (Phase 4A).
- SARIF parser or analyser execution (Phase 6).
- Any LLM calls or embeddings.
- Any patch generation, workflow orchestration, or evaluation runners.
- Anything requiring the Phase 1 schema to be complete.

Phase 0 modules must be real (importable, testable, with stubs for their intended interfaces) but their implementations are empty, raise `NotImplementedError`, or return clearly marked placeholder values.

---

## 3. Package Name And Namespace

The recommended package name is `llm_sca_tooling`. The distribution name is `llm-sca-tooling`.

All source code lives under `src/llm_sca_tooling/`. This layout keeps the source tree separate from tests and project root files and avoids implicit namespace pollution during development.

If the project adopts a different package name, preserve the module boundary structure and test coverage requirements described below.

---

## 4. Recommended Package Layout

```text
llm-sca-tooling/
├── .agent/
│   ├── plan.md                          # session plan template (from Phase H0)
│   └── skills/                          # SKILL.md templates (from Phase H0)
├── .github/
│   └── workflows/
│       ├── ci.yml                       # lint, type check, tests, secrets, dep scan
│       └── governance.yml               # manifest non-relaxation and drift checks
├── docs/
│   └── architecture-notes.md            # pointer to llm-sca-tooling-architecture.md
├── fixtures/
│   └── repos/
│       ├── tiny-python/                 # minimal Python repo fixture
│       └── tiny-multi/                  # minimal multi-file repo fixture
├── schemas/
│   └── run-record.schema.json           # stub schema file (populated in Phase 1)
├── src/
│   └── llm_sca_tooling/
│       ├── __init__.py                  # version, package metadata
│       ├── config.py                    # configuration model
│       ├── errors.py                    # structured error types
│       ├── telemetry/
│       │   ├── __init__.py
│       │   ├── logging.py               # structured logger setup
│       │   └── trace_writer.py          # session telemetry JSONL writer skeleton
│       ├── schemas/                     # placeholder; populated in Phase 1
│       │   └── __init__.py
│       ├── graph/                       # placeholder; populated in Phase 3
│       │   └── __init__.py
│       ├── indexing/                    # placeholder; populated in Phase 3
│       │   └── __init__.py
│       ├── mcp_server/
│       │   ├── __init__.py
│       │   └── server.py                # placeholder MCP server entrypoint
│       ├── plugins/
│       │   ├── __init__.py
│       │   └── registry.py              # plugin registry skeleton
│       ├── sarif/                       # placeholder; populated in Phase 6
│       │   └── __init__.py
│       ├── workflows/                   # placeholder; populated in Phase 13+
│       │   └── __init__.py
│       ├── evaluation/                  # placeholder; populated in Phase 10
│       │   └── __init__.py
│       ├── harness/
│       │   ├── __init__.py
│       │   └── condition.py             # Harness Condition Sheet writer skeleton
│       ├── memory/                      # placeholder; populated in Phase 17
│       │   └── __init__.py
│       ├── operations/
│       │   ├── __init__.py
│       │   ├── run_records.py           # run-record writer skeleton
│       │   └── budget.py                # budget monitor skeleton
│       ├── governance/
│       │   ├── __init__.py
│       │   ├── policy.py                # policy evaluator skeleton
│       │   └── permissions.py           # permission profile skeleton
│       └── cli/
│           ├── __init__.py
│           └── main.py                  # CLI entrypoint
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_errors.py
│   │   ├── test_telemetry.py
│   │   ├── test_trace_writer.py
│   │   ├── test_run_records.py
│   │   ├── test_budget.py
│   │   ├── test_policy.py
│   │   ├── test_permissions.py
│   │   ├── test_plugin_registry.py
│   │   ├── test_harness_condition.py
│   │   └── test_cli.py
│   ├── smoke/
│   │   └── test_smoke_install.py
│   └── harness/
│       ├── test_manifest_regression.py  # stubs from Phase H0
│       ├── test_semantic_mutation.py    # stubs from Phase H0
│       └── test_non_relaxation.py       # stubs from Phase H0
├── AGENTS.md                            # from Phase H0
├── CLAUDE.md                            # from Phase H0
├── Makefile                             # verify, test, lint, format targets
├── pyproject.toml
├── tox.ini
└── uv.lock
```

---

## 5. Dependency Management

### 5.1 Tooling Choice

Use `uv` as the package and environment manager. All Python commands in documentation, CI, and `AGENTS.md` must be prefixed with `uv run`.

Rationale: `uv` produces a lockfile (`uv.lock`) that pins exact versions of all direct and transitive dependencies, satisfying the supply-chain requirements from Phase H0.

### 5.2 pyproject.toml Structure

The authoritative dependency list lives in `llm-sca-tooling-tech-stack.md` §16. The excerpt below reflects the Phase 0 starting state (later phases activate commented entries).

```toml
[project]
name = "llm-sca-tooling"
version = "0.1.0"
description = "LLM-augmented static code analysis tooling"
requires-python = ">=3.12"
dependencies = [
    # core data / config
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
    # embeddings — uncomment in Phase 9
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
]

[project.scripts]
llm-sca-tooling = "llm_sca_tooling.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/llm_sca_tooling"]

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
]

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

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
[[tool.mypy.overrides]]
module = ["networkx.*", "tree_sitter.*", "pyan.*"]
ignore_missing_stubs = true

[tool.bandit]
exclude_dirs = ["tests"]
```

### 5.3 Version Pinning Policy

- Direct dependencies must have lower-bound pins (`>=`).
- The `uv.lock` file pins exact versions.
- Security-sensitive tools (secrets scanners, SAST, dependency auditors) must have their versions recorded in the supply-chain ledger and the Harness Condition Sheet for any run that uses them.
- `uv lock --upgrade` runs are treated as a dependency-update event and require a dependency scan CI pass before merge.

### 5.4 Runtime Version Reporting

The CLI must be able to report its runtime environment:

```bash
llm-sca-tooling version
```

Output must include:

```text
llm-sca-tooling: 0.1.0
python: 3.12.x
uv: x.x.x
```

The Harness Condition Sheet writer must be able to call the same version reporter.

---

## 6. Configuration Model

### 6.1 Design Principles

- Configuration is explicit. No hard-coded paths, ports, or credentials anywhere in the package.
- Configuration is typed. The configuration class uses Pydantic v2 with strict validation.
- Configuration is layered: defaults < config file < environment variables.
- Sensitive values (API keys, tokens) must never appear in log output or stored artefacts.

### 6.2 Configuration Model Skeleton

```python
# src/llm_sca_tooling/config.py

from pydantic import BaseModel, field_validator
from pathlib import Path


class TelemetryConfig(BaseModel):
    trace_dir: Path = Path(".agent/traces")
    enabled: bool = True


class BudgetConfig(BaseModel):
    max_tokens: int = 100_000
    max_tool_calls: int = 200
    max_retries: int = 3
    max_wall_seconds: int = 3600


class PolicyConfig(BaseModel):
    permission_profile: str = "read-only"
    path_allowlist: list[str] = []
    network_deny_by_default: bool = True


class MCPConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    dev_mode: bool = True


class Config(BaseModel):
    model_config = {"extra": "forbid"}

    package_name: str = "llm-sca-tooling"
    version: str = "0.1.0"
    workspace_root: Path = Path(".")
    telemetry: TelemetryConfig = TelemetryConfig()
    budget: BudgetConfig = BudgetConfig()
    policy: PolicyConfig = PolicyConfig()
    mcp: MCPConfig = MCPConfig()
```

### 6.3 Configuration Loading

Implement a `load_config(path: Path | None = None) -> Config` function that:

1. Loads defaults from the model.
2. Overlays a TOML or JSON config file if `path` is given or if a default config path exists.
3. Overlays environment variables with the prefix `LLM_SCA_`.
4. Validates the result with Pydantic.
5. Raises a typed `ConfigError` (not a bare `ValueError`) if validation fails.

### 6.4 CLI Config Command

The CLI must expose:

```bash
llm-sca-tooling config show     # print current configuration (with sensitive fields redacted)
llm-sca-tooling config validate  # validate the config file and exit 0 on success
```

---

## 7. Logging And Structured Error Model

### 7.1 Logging Setup

All modules use the standard `logging` module. No `print()` calls anywhere in production code.

Create a `get_logger(name: str) -> logging.Logger` helper in `llm_sca_tooling.telemetry.logging` that:

- Returns a logger with the given name.
- Configures a structured formatter on first call (timestamp, level, logger name, message).
- Respects `LLM_SCA_LOG_LEVEL` environment variable.
- Does not add duplicate handlers if called multiple times.

**RichHandler integration**: in CLI contexts, the root logger is configured with `RichHandler` in `llm_sca_tooling.cli.main` before any module is imported. The `get_logger` helper must not add its own handler if a handler is already present on the root logger. This ensures log output and Rich-rendered output do not interleave in the terminal.

In non-CLI contexts (tests, background tasks, CI), `get_logger` adds a plain `StreamHandler` with a structured format. Rich is restricted to the `cli` layer only — other modules must not import `rich` directly.

Log level conventions (from global preferences):

```text
DEBUG    diagnostic details, variable values, intermediate states
INFO     milestones, phase transitions, successful completions
WARNING  recoverable issues, stale evidence, degraded mode
ERROR    failures that prevent a task from completing
```

### 7.2 Lazy Formatting

All log calls must use lazy formatting:

```python
# correct
logger.info("Indexing %d files in %s", file_count, repo_path)

# incorrect - do not do this
logger.info(f"Indexing {file_count} files in {repo_path}")
```

### 7.3 Exception Logging

Exceptions must be logged with `logger.exception()` or `exc_info=True` so the traceback is captured:

```python
try:
    do_something()
except SomeSpecificError as exc:
    logger.error("Failed to process %s: %s", item_id, exc, exc_info=True)
    raise OperationError("Processing failed") from exc
```

### 7.4 Structured Error Types

Create a hierarchy of typed exceptions in `llm_sca_tooling.errors`:

```python
class LLMSCAError(Exception):
    """Base exception for all llm-sca-tooling errors."""

class ConfigError(LLMSCAError):
    """Configuration is invalid or missing."""

class PolicyViolationError(LLMSCAError):
    """An operation was denied by the policy engine."""

class BudgetExhaustedError(LLMSCAError):
    """A budget limit was exceeded."""

class PluginError(LLMSCAError):
    """A plugin failed to load or execute."""

class SchemaValidationError(LLMSCAError):
    """A schema object failed validation."""

class NotImplementedFeatureError(LLMSCAError):
    """A feature that is planned but not yet implemented was called."""
```

`NotImplementedFeatureError` is used instead of bare `NotImplementedError` in skeleton modules so that callers can distinguish between Python's built-in `NotImplementedError` (operator not supported) and a planned-but-unimplemented product feature.

---

## 8. Session Telemetry Skeleton

### 8.1 Trace Writer

Implement a minimal trace writer in `llm_sca_tooling.telemetry.trace_writer` that satisfies the Phase H0 telemetry contract.

Required interface:

```python
class TraceWriter:
    def __init__(self, session_id: str, trace_dir: Path) -> None: ...

    def emit(self, event_type: str, actor: str, stage: str, **fields: object) -> None:
        """Append a trace event to the session JSONL file."""

    def session_start(self) -> None: ...
    def session_end(self, status: str) -> None: ...
    def tool_call(self, tool_name: str, category: str, policy_action: str, **kwargs: object) -> None: ...
    def verification_event(self, check_name: str, outcome: str, artefact_ids: list[str]) -> None: ...
```

Implementation requirements:

- Events are written as newline-delimited JSON to `{trace_dir}/{session_id}.jsonl`.
- Every event carries `event_id`, `session_id`, `seq`, `ts`, `type`, `actor`, `stage`, `redaction_status`.
- Sequence numbers are monotonically increasing within a session.
- The writer must be thread-safe (use a lock or write to a queue).
- If `trace_dir` does not exist, the writer creates it.
- Sensitive fields must be redacted before writing (use a `redact_sensitive_fields` helper that strips known-sensitive key patterns).

### 8.2 Harness Condition Sheet Writer

Implement a minimal Harness Condition Sheet writer in `llm_sca_tooling.harness.condition`:

```python
class HarnessConditionWriter:
    def capture(
        self,
        run_id: str,
        phase: str,
        runtime_version: str,
        model_backend: str,
        toolset_hash: str,
        permission_profile: str,
        context_budget: int | None,
        gates_enabled: list[str],
        gates_disabled: list[str],
        trace_location: str | None,
        trace_completeness: str,
        redaction_policy: str,
    ) -> dict[str, object]:
        """Return a Harness Condition Sheet dict and optionally persist it."""
```

The returned dict must match the Harness Condition Sheet template from Phase H0.

---

## 9. Run-Record Writer Skeleton

Implement the run-record writer in `llm_sca_tooling.operations.run_records`.

### 9.1 Required Interface

```python
class RunRecord:
    run_id: str
    workflow: str
    status: str  # running | complete | failed | incomplete | unknown | budget-exhausted
    events: list[dict[str, object]]

class RunRecordWriter:
    def create_run(
        self,
        workflow: str,
        repos: list[str],
        model_backend: str,
        policy_id: str,
        permission_profile: str,
        context_budget: int | None,
        redaction_policy: str,
    ) -> str:
        """Create a new run record and return run_id."""

    def append_event(
        self,
        run_id: str,
        event_type: str,
        actor: str,
        stage: str,
        policy_action: str,
        **fields: object,
    ) -> str:
        """Append a run event and return event_id."""

    def close_run(
        self,
        run_id: str,
        status: str,
        final_verdict_id: str | None = None,
        harness_condition_id: str | None = None,
    ) -> None:
        """Close a run with final status."""

    def get_run(self, run_id: str) -> RunRecord | None: ...
```

### 9.2 Implementation Requirements

Phase 0 implementation must:

- Use file-based storage (a JSONL file per run under `.agent/runs/`).
- Generate high-entropy `run_id` values (e.g. `run:<ulid>` or `run:<uuid4>`).
- Generate sequential `event_id` values within the run.
- Reject event appends to a closed run.
- Be importable and testable without any Phase 1 schema objects.

Phase 4A will replace the storage backend with a proper store; the interface must remain compatible.

---

## 10. Policy Evaluator Skeleton

Implement the policy evaluator skeleton in `llm_sca_tooling.governance.policy`.

### 10.1 Required Interface

```python
class PolicyDecision:
    action: str  # allow | deny | approval_required | blocked
    reason: str
    policy_id: str

class PolicyEvaluator:
    def evaluate_tool_call(
        self,
        tool_name: str,
        tool_category: str,
        permission_profile: str,
        requested_path: str | None = None,
        network_required: bool = False,
    ) -> PolicyDecision:
        """Return allow/deny/approval_required for a proposed tool call."""
```

### 10.2 Implementation Requirements

Phase 0 implementation must:

- Return `deny` for any tool in a category not allowed by the given permission profile.
- Return `deny` for writes outside the path allowlist when a path is provided.
- Return `deny` for any network-requiring tool when `network_deny_by_default` is `True`.
- Return `approval_required` for `execute` and `commit` categories in non-`scoped-execute` profiles.
- Return `allow` for `read` and `search` categories in all profiles.
- Record every decision as a log event at `DEBUG` level.

Phase 4A will replace this stub with a full policy engine backed by the Phase 1 schemas.

---

## 11. Budget Monitor Skeleton

Implement the budget monitor skeleton in `llm_sca_tooling.operations.budget`.

### 11.1 Required Interface

```python
class BudgetStatus:
    tokens_used: int
    tokens_limit: int | None
    tool_calls_used: int
    tool_calls_limit: int | None
    wall_seconds_used: float
    wall_seconds_limit: int | None
    retries_used: int
    retries_limit: int | None
    status: str  # ok | soft_warning | hard_stop

class BudgetMonitor:
    def record_tokens(self, count: int) -> BudgetStatus: ...
    def record_tool_call(self) -> BudgetStatus: ...
    def record_retry(self) -> BudgetStatus: ...
    def check_wall_clock(self) -> BudgetStatus: ...
    def reset(self) -> None: ...
```

### 11.2 Implementation Requirements

- `BudgetStatus.status` is `soft_warning` when any metric exceeds 80% of its limit.
- `BudgetStatus.status` is `hard_stop` when any metric meets or exceeds its limit.
- A `hard_stop` status must be propagated to the run record as a `budget_hard_stop` event by the caller.
- The monitor must not suppress `hard_stop` silently. Callers must handle it explicitly.

---

## 12. Permission Profile Skeleton

Implement the permission profile skeleton in `llm_sca_tooling.governance.permissions`.

### 12.1 Required Interface

```python
class PermissionProfile:
    name: str  # read-only | plan | scoped-edit | scoped-execute | review-commit
    allowed_categories: list[str]
    path_allowlist: list[str]
    network_allowed: bool
    require_approval_for: list[str]

class PermissionProfileLoader:
    def load(self, profile_name: str) -> PermissionProfile:
        """Load a named permission profile from config or built-in defaults."""

    def list_profiles(self) -> list[str]:
        """Return names of all available profiles."""
```

### 12.2 Built-in Profiles

| Profile | Allowed categories | Network |
|---|---|---|
| `read-only` | `read`, `search` | No |
| `plan` | `read`, `search`, plus `edit` for `.agent/plan.md` only | No |
| `scoped-edit` | `read`, `search`, `edit` within path scope | No |
| `scoped-execute` | `read`, `search`, `edit`, `execute` within allowlist | No |
| `review-commit` | All | No (network requires separate allow) |

---

## 13. CLI Entrypoint

Implement the CLI using **Typer** and **Rich** in `llm_sca_tooling.cli.main`. The entry point registered in `pyproject.toml` is `llm_sca_tooling.cli.main:app`.

### 13.1 Required Commands In Phase 0

```bash
llm-sca-tooling --version                # print package version (Typer built-in)
llm-sca-tooling config show              # print current config (redacted, Rich table)
llm-sca-tooling config validate          # validate config and exit 0/1
llm-sca-tooling harness status           # print harness stage + readiness score (Rich table)
llm-sca-tooling run create <workflow>    # create a dummy run record (for testing)
llm-sca-tooling mcp start                # start MCP server in dev mode
```

Typer app skeleton:

```python
import typer
from rich.console import Console

app = typer.Typer(name="llm-sca-tooling", no_args_is_help=True)
console = Console()
config_app = typer.Typer()
app.add_typer(config_app, name="config")
```

### 13.2 Rich Integration

The CLI entry point must configure `RichHandler` before any module logs output:

```python
import logging
from rich.logging import RichHandler

def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
```

Use `Console` for structured output (tables, panels). Do not mix `typer.echo` and Rich output in the same command — choose one per command.

### 13.3 Error Handling

CLI commands must:

- Return exit code 0 on success.
- Raise `typer.Exit(code=1)` on handled errors (config invalid, file not found, etc.).
- Raise `typer.Exit(code=2)` on unhandled exceptions caught at the top level.
- Never display raw tracebacks to the user; log them at `ERROR` level with `exc_info=True`.
- Display a short, actionable error message via `console.print("[red]Error:[/red] ...")`.

---

## 14. Placeholder MCP Server Entrypoint

Implement a minimal MCP server in `llm_sca_tooling.mcp_server.server` that:

- Starts and logs `"MCP server started in dev mode on {host}:{port}"` at `INFO` level.
- Responds to a health check or ping.
- Logs its version and configuration on startup.
- Does not expose any tools, resources, or prompts yet (those come in Phase 4).
- Raises `NotImplementedFeatureError` for any MCP request beyond health checks.

The server must be startable from the CLI via `llm-sca-tooling mcp start` and from a test via `server.start(config)`.

---

## 15. Plugin Registry Skeleton

Implement the plugin registry skeleton in `llm_sca_tooling.plugins.registry`.

### 15.1 Required Interface

```python
class PluginCapabilities:
    detect: bool = False
    index: bool = False
    link: bool = False
    traverse: bool = False

class Plugin:
    plugin_id: str
    name: str
    version: str
    capabilities: PluginCapabilities

class PluginRegistry:
    def register(self, plugin: Plugin) -> None: ...
    def load(self, plugin_id: str) -> Plugin | None: ...
    def list_plugins(self) -> list[Plugin]: ...
    def reload(self, plugin_id: str | None = None) -> None:
        """Re-run plugin indexing pass for one or all plugins."""
```

### 15.2 No-Op Plugin

Create a built-in `NoOpPlugin` that implements all interfaces and does nothing. It must be loadable via `plugin_registry.load("noop")`. The `NoOpPlugin` is used in tests to verify that the registry loads and invokes plugins correctly without requiring a real plugin.

---

## 16. Fixture Repositories For Tests

Create two minimal fixture repositories under `fixtures/repos/`:

### 16.1 tiny-python

A minimal Python repository with:

```text
fixtures/repos/tiny-python/
├── src/
│   └── tiny/
│       ├── __init__.py          # version = "0.1.0"
│       └── math_utils.py        # add(a, b), divide(a, b) with a divide-by-zero bug
├── tests/
│   └── test_math_utils.py       # tests for add and divide
└── pyproject.toml               # minimal pyproject, no build deps
```

The divide-by-zero bug is intentional. It provides a fixture issue for later fault-localisation tests.

### 16.2 tiny-multi

A minimal multi-file repository with cross-file imports:

```text
fixtures/repos/tiny-multi/
├── src/
│   └── multi/
│       ├── __init__.py
│       ├── models.py            # simple dataclasses
│       ├── processor.py         # imports models.py; has a latent type error
│       └── api.py               # imports processor.py; exposes a function
├── tests/
│   └── test_api.py
└── pyproject.toml
```

The latent type error in `processor.py` provides a fixture for SARIF and static-analysis tests.

Both fixture repos must be valid Python and must have a test suite that passes (the bugs are in implementation, not test infrastructure).

---

## 17. Test Infrastructure

### 17.1 Test Runner

See `llm-sca-tooling-tech-stack.md` §5 for the full testing stack rationale. The `pyproject.toml` configuration is set in §5.2 of this document. Key settings:

- `asyncio_mode = "auto"` — all `async def test_` functions run without decorators.
- `pytest-xdist` enabled via `-n auto` for parallel execution on Phase 10+ test suites.
- `unittest.TestCase` subclasses are discovered and run by pytest automatically.

**Async test example:**

```python
async def test_run_record_lifecycle() -> None:
    writer = RunRecordWriter(base_dir=tmp_path)
    run_id = await writer.create_run("test-workflow", repos=[], ...)
    event_id = await writer.append_event(run_id, "gate", actor="agent", ...)
    await writer.close_run(run_id, status="complete")
    record = await writer.get_run(run_id)
    assert record is not None
    assert len(record.events) == 1
```

### 17.2 Coverage Requirements

| Module | Required coverage |
|---|---|
| `config.py` | ≥95% |
| `errors.py` | ≥95% |
| `telemetry/` | ≥95% |
| `operations/` | ≥95% |
| `governance/` | ≥90% |
| `plugins/registry.py` | ≥90% |
| `harness/condition.py` | ≥90% |
| `cli/main.py` | ≥85% |
| `mcp_server/server.py` | ≥85% |

Skeleton modules with only `NotImplementedFeatureError` stubs do not count toward coverage targets; coverage is measured on the logic that is actually implemented in Phase 0.

### 17.3 Tox Configuration

Configure `tox.ini` to run on Python 3.12 and 3.13 (when available):

```ini
[tox]
envlist = py312, py313

[testenv]
deps = uv
commands =
    uv run pytest {posargs}
```

### 17.4 Conftest

`tests/conftest.py` should provide:

- A `config` fixture that returns a `Config` with test defaults (temp directory for trace output, etc.).
- A `run_record_writer` fixture that creates a `RunRecordWriter` backed by a temp directory.
- A `budget_monitor` fixture with tight limits useful for testing `hard_stop` behaviour.
- A `tiny_python_repo` fixture that returns the path to `fixtures/repos/tiny-python`.

---

## 18. CI Workflow

### 18.1 ci.yml

The CI workflow runs on pull requests and main-branch pushes.

Required jobs:

| Job | Steps |
|---|---|
| `lint-and-type-check` | `uv run isort --check .`, `uv run black --check .`, `uv run ruff check .`, `uv run mypy src/` |
| `test` | `uv run pytest --cov=src --cov-report=term-missing tests/unit/ tests/smoke/` |
| `secrets-scan` | `detect-secrets scan` |
| `dependency-audit` | `uv run pip-audit` |
| `sast` | `uv run bandit -r src/` |

All jobs must pass before a pull request can be merged.

### 18.2 governance.yml

A separate governance workflow runs manifest non-relaxation checks:

- Detect if `AGENTS.md` HC1–HC6 constraints have been removed or weakened.
- Detect if any runtime overlay contradicts `AGENTS.md`.
- Run the harness regression stubs from `tests/harness/test_non_relaxation.py`.

This workflow blocks merge on `relaxed` drift.

---

## 19. Exit Criteria

### Source Plan Exit Criterion

Package installs locally.

**Concrete Phase 0 acceptance:**

- `uv install` (or `pip install -e .`) completes without error.
- `python -c "import llm_sca_tooling"` succeeds.

---

### Source Plan Exit Criterion

Test suite runs.

**Concrete Phase 0 acceptance:**

- `uv run pytest tests/unit/ tests/smoke/` passes.
- `uv run pytest --cov=src --cov-report=term-missing tests/unit/` reports coverage meeting or exceeding the module targets in §17.2.
- No test failures, no skipped tests without documented reasons.

---

### Source Plan Exit Criterion

Local verify command runs the same core checks expected before merge.

**Concrete Phase 0 acceptance:**

- `make verify` (or equivalent) runs: isort check, black check, ruff check, mypy, pytest unit, secrets scan, dependency audit, bandit.
- All checks pass on an unmodified clean checkout.
- The verify command is documented in `AGENTS.md` and `CLAUDE.md`.

---

### Source Plan Exit Criterion

CLI can print version and config.

**Concrete Phase 0 acceptance:**

- `llm-sca-tooling --version` prints the package version.
- `llm-sca-tooling config show` prints the current configuration with sensitive fields redacted.
- `llm-sca-tooling config validate` exits 0 on a valid config and 1 on an invalid config.

---

### Source Plan Exit Criterion

Empty MCP server can start in development mode.

**Concrete Phase 0 acceptance:**

- `llm-sca-tooling mcp start` starts the MCP server and logs its startup message.
- The server can be started and stopped in a test without hanging.
- The server does not crash on a health check request.

---

### Source Plan Exit Criterion

Plugin registry can load a no-op plugin.

**Concrete Phase 0 acceptance:**

- `PluginRegistry().load("noop")` returns the `NoOpPlugin`.
- `PluginRegistry().list_plugins()` returns a non-empty list after registration.
- Plugin tests pass.

---

### Source Plan Exit Criterion

Runtime/tool versions and the active Harness Condition Sheet can be printed.

**Concrete Phase 0 acceptance:**

- `llm-sca-tooling harness status` prints the harness stage, per-axis readiness score, and active permission profile.
- `HarnessConditionWriter().capture(...)` returns a dict that includes all required fields from the Phase H0 template.

---

### Source Plan Exit Criterion

A dummy run can create a run record, append an event, and close with a status.

**Concrete Phase 0 acceptance:**

- `RunRecordWriter().create_run(...)` returns a non-empty `run_id`.
- `RunRecordWriter().append_event(run_id, ...)` returns a non-empty `event_id`.
- `RunRecordWriter().close_run(run_id, status="complete")` completes without error.
- `RunRecordWriter().get_run(run_id)` returns the run with the appended event.
- Attempting to append to a closed run raises a `RuntimeError` or equivalent typed error.

---

## 20. Definition Of Done

Phase 0 is done when:

- The package installs locally.
- `uv run pytest tests/unit/ tests/smoke/` passes with required coverage.
- `make verify` passes on an unmodified checkout.
- `llm-sca-tooling --version` prints the version.
- `llm-sca-tooling mcp start` starts the server and can be stopped cleanly.
- All skeleton modules are importable without errors.
- `NotImplementedFeatureError` is raised (not `NotImplementedError`) for unimplemented features.
- The `NoOpPlugin` loads via the plugin registry.
- A dummy run record can be created, event appended, and run closed.
- The CI workflow passes on a clean main branch.
- The governance workflow detects HC1–HC6 relaxation in a test mutation.
- Both fixture repositories (`tiny-python` and `tiny-multi`) pass their own test suites.
- The `AGENTS.md` and `CLAUDE.md` from Phase H0 are present and referenced in the verify command.
- Module coverage meets targets from §17.2.

---

## 21. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Package name chosen without checking PyPI | Distribution name conflict | Check PyPI before finalising the name in `pyproject.toml` |
| Skeleton modules use `pass` instead of `NotImplementedFeatureError` | Phase 1+ code silently succeeds on unimplemented operations | Require `NotImplementedFeatureError` in stubs; add a lint rule or test |
| MCP library version not yet pinned | Phase 4 must re-do dependency setup | Add MCP library as a commented-out dependency with version constraint noted |
| Coverage target not set in CI | Coverage degrades silently as code is added | Add `--cov-fail-under=<threshold>` to pytest CI step |
| Fixture repository bugs are too simple | Phase 9 FL tests trivially pass | Keep bugs realistic: divide-by-zero triggered only in specific call path; type error requires cross-file analysis |
| Run-record writer uses ad-hoc storage | Phase 4A cannot reuse it cleanly | Define the interface contract clearly; Phase 4A replaces storage, not the interface |
| CLI tests require a running MCP server | Tests become slow or flaky | Use a test-only server fixture with a short startup timeout; keep integration tests in `smoke/` not `unit/` |
| tox is slow on first run | Developer experience degrades | Cache `uv` environments; document `uv run pytest` as the fast path for local development |

---

## 22. Phase 0 Completion Report Template

When Phase 0 implementation is complete, report:

```text
Phase 0 completion report

Implemented:
- Package name and version:
- Python version floor:
- Dependency manager:
- Module count (importable):
- Skeleton modules with NotImplementedFeatureError:
- CLI commands implemented:
- MCP server: placeholder | not yet
- Plugin registry: skeleton | not yet
- Run-record writer: skeleton | not yet
- Budget monitor: skeleton | not yet
- Policy evaluator: skeleton | not yet
- Permission profile loader: skeleton | not yet
- Harness condition writer: skeleton | not yet

Verification:
- Unit tests:
- Smoke tests:
- Coverage (key modules):
- Verify command passes: Yes | No
- CI workflow green: Yes | No
- Governance workflow detects relaxation mutation: Yes | No

Exit criteria:
- Package installs:
- Test suite passes:
- Local verify passes:
- CLI version/config:
- MCP server starts:
- Plugin registry loads NoOpPlugin:
- Harness status printable:
- Dummy run record lifecycle:

Known limitations:
-

Follow-up for Phase 1:
-
```

---

## 23. Minimal First Slice Within Phase 0

If Phase 0 needs to be split further, implement this first:

1. Create `pyproject.toml`, `uv.lock`, and `Makefile` with the `verify` target.
2. Create `src/llm_sca_tooling/__init__.py` with `__version__`.
3. Create `llm_sca_tooling.config` with the `Config` model and `load_config`.
4. Create `llm_sca_tooling.errors` with the exception hierarchy.
5. Create `llm_sca_tooling.telemetry.logging` with `get_logger`.
6. Create `llm_sca_tooling.cli.main` with `--version` and `config show`.
7. Create the test conftest and the first unit tests for `config` and `errors`.
8. Run `make verify` and confirm it passes.

The remaining modules (trace writer, run-record writer, budget monitor, policy evaluator, permission profile, MCP server, plugin registry, harness condition writer) can follow in a second slice. The fixture repositories can be added in a third slice alongside their conftest fixtures.
