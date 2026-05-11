#!/usr/bin/env bash
# Post-create setup for the evidence-sca devcontainer.
# Installs uv, system tools, and project dependencies.
# Secrets are NOT mounted. EVIDENCE_SCA_WORKSPACE must be set by the container env.

set -euo pipefail

echo "=== evidence-sca devcontainer post-create ==="

# Install uv
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install system tools required by the toolchain
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    universal-ctags \
    semgrep \
    git \
    curl \
    jq \
    2>/dev/null || true

# Install project dependencies
cd /workspace
uv sync

# Pre-commit hooks
uv run pre-commit install --install-hooks || true

# Create workspace directory
mkdir -p "${EVIDENCE_SCA_WORKSPACE:-.evidence-sca}"

echo ""
echo "=== Setup complete ==="
echo "  EVIDENCE_SCA_WORKSPACE: ${EVIDENCE_SCA_WORKSPACE}"
echo ""
echo "Quick start:"
echo "  llm-sca-tooling config validate"
echo "  llm-sca-tooling harness status"
echo "  llm-sca-tooling mcp serve --transport stdio"
echo ""
echo "Required environment variables (set in .env or container env):"
echo "  EVIDENCE_SCA_WORKSPACE  - workspace root (already set)"
echo "  HATCH_INDEX_AUTH        - PyPI token for releases (do NOT commit)"
echo ""
echo "Secrets are NOT mounted. See docs/installation.md for configuration."
