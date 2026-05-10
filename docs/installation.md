# Installation

Install the package with uv for local development:

```bash
uv sync --extra dev
uv run llm-sca-tooling --version
uv run evidence-sca --version
```

Install from a built wheel:

```bash
uv build
uv pip install dist/*.whl
```

Runtime entrypoints:

- `llm-sca-tooling`: governance, replay, diagnosis, release gates, and MCP smoke commands.
- `evidence-sca`: indexing and local MCP compatibility commands.

Every operational run should link to a HarnessConditionSheet before release use.

## Limitations

Network access is deny-by-default. Optional HTTP MCP mode validates hardened
configuration, but production deployment still needs an operator-owned TLS and
process supervisor setup.
