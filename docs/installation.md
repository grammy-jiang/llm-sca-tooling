# Installation Guide

> This guide covers installing `evidence-sca` (llm-sca-tooling) on a developer workstation
> or CI runner. For devcontainer quick-start, see [Devcontainer](#devcontainer-quick-start).

---

## Limitations

- `evidence-sca` does **not** produce results that are correct without evidence. All quality
  claims reference the Phase 18 calibration reports. See the [Evaluation Guide](evaluation-guide.md).
- Language backends are limited to languages with a `ctags` parser or a registered plugin.
  See [Plugin Authoring Guide](plugin-authoring-guide.md) for extension.
- LLM-assisted workflows require an LLM API key; null-mode smoke evals work without one.
- The tool cannot replace code review. It produces evidence-graded findings; humans review them.
- A `HarnessConditionSheet` must be completed for every release or evaluation run that
  claims a quality verdict. See [Harness Setup Guide](harness-setup-guide.md).

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Older versions are not supported |
| `uv` | latest | Recommended package manager |
| `universal-ctags` | any | Required for graph indexing |
| `semgrep` | ≥1.0 | Required for SAST workflows |
| `git` | ≥2.30 | Required for blame chains and git hook integration |

### Installing system prerequisites

**macOS (Homebrew):**
```bash
brew install python@3.12 uv universal-ctags semgrep git
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv git universal-ctags
# uv:
curl -LsSf https://astral.sh/uv/install.sh | sh
# semgrep (via pip or package manager):
pip install semgrep
```

**Windows (WSL2 recommended):** Use the Ubuntu instructions inside WSL2.

---

## Installation

### Option A: Install from PyPI (recommended)

```bash
uv add evidence-sca
# or:
pip install evidence-sca
```

### Option B: Install from source

```bash
git clone https://github.com/your-org/evidence-sca.git
cd evidence-sca
uv sync
```

### Option C: Development install with all extras

```bash
uv sync --all-groups
pre-commit install
```

---

## Initial Configuration

### 1. Create a workspace

```bash
llm-sca-tooling config validate
# Creates ~/.evidence-sca/config.toml if it does not exist
```

Or specify a custom workspace:

```bash
export EVIDENCE_SCA_WORKSPACE=/path/to/workspace
llm-sca-tooling config validate
```

### 2. Validate the configuration

```bash
llm-sca-tooling config show   # shows current config with sensitive fields redacted
llm-sca-tooling config validate  # exits 0 on success, 1 on error
```

### 3. Required environment variables

| Variable | Required | Description |
|---|---|---|
| `EVIDENCE_SCA_WORKSPACE` | No (defaults to `~/.evidence-sca`) | Workspace root directory |
| `LLM_API_KEY` | For LLM workflows only | API key for LLM backend |
| `HATCH_INDEX_AUTH` | For releases only | PyPI upload token — **never commit** |

All secrets must be stored in environment variables or a secrets manager.
**Never hardcode credentials (HC1).**

---

## MCP Server Startup

### stdio transport (default)

```bash
llm-sca-tooling mcp serve --transport stdio
```

Configure your MCP client (e.g., Claude Code, VS Code Copilot) to launch this command.

### Streamable HTTP transport

```bash
llm-sca-tooling mcp serve --transport http --host 127.0.0.1 --port 8080
```

**Security rules for HTTP transport:**
- TLS is required for non-localhost deployments.
- Set `auth_token_env_var` in your config when `single_user: false`.
- CORS allowed origins must be explicitly listed; wildcard `*` is rejected.

---

## Devcontainer Quick-Start

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) in VS Code.
2. Open the `evidence-sca` repository folder in VS Code.
3. When prompted, click **Reopen in Container** (or run `Dev Containers: Reopen in Container`).
4. The container installs Python 3.12, `uv`, `universal-ctags`, `semgrep`, and all project
   dependencies automatically via `.devcontainer/postCreate.sh`.
5. The MCP server starts automatically in the background.

The devcontainer sets `EVIDENCE_SCA_WORKSPACE=/workspace/.evidence-sca`.
Secrets are **not** mounted automatically; set them in VS Code's secrets store or your shell profile.

---

## Verifying the Installation

```bash
llm-sca-tooling --version
llm-sca-tooling config validate
llm-sca-tooling harness status
```

Expected output of `harness status`:
```
Stage: S2 (or higher)
Score: ...
Active permission profile: read_search_edit
```

---

## Next Steps

- [Quickstart Guide](quickstart.md) — register a repo and run your first workflow.
- [Harness Setup Guide](harness-setup-guide.md) — configure AGENTS.md and permission profiles.
- [Architecture Overview](architecture.md) — understand the five product surfaces.
