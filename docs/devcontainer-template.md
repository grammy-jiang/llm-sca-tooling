# Devcontainer Template

This repository's agent scope does not allow writing `.devcontainer/` directly.
Operators can adapt this template manually when they need an isolated developer
container.

```json
{
  "name": "evidence-sca",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },
  "postCreateCommand": "pipx install uv && uv sync --extra dev",
  "customizations": {
    "vscode": {
      "settings": {
        "python.defaultInterpreterPath": ".venv/bin/python"
      }
    }
  }
}
```

Record any containerized verification in the HarnessConditionSheet.

## Limitations

The template is intentionally minimal and does not grant network or secret
access. Add organization-specific mounts, caches, and credentials outside agent
authored changes.
