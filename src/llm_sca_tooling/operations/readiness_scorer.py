"""Readiness scorer.

Wraps the AI-readiness assessment and returns a per-axis numeric score map
plus a total score, suitable for the ``compute_readiness_score`` MCP tool.

Six axes (0–20 each, total 0–120):
  1. agent_config       — AGENTS.md, skills, overlays
  2. docs_spec          — docs/*.md, architecture doc references
  3. ci_build           — Makefile, .github/workflows, tox.ini, pre-commit
  4. code_structure     — src/, tests/, pyproject.toml
  5. security_scanning  — ruff, mypy, detect-secrets, bandit, pip-audit
  6. deterministic_gates — verify gate (make verify), tox, pre-commit hooks
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["ReadinessScore", "compute_readiness_score"]

_MAX_AXIS = 20


@dataclass
class ReadinessScore:
    repo_root: str
    agent_config: int = 0
    docs_spec: int = 0
    ci_build: int = 0
    code_structure: int = 0
    security_scanning: int = 0
    deterministic_gates: int = 0

    @property
    def total(self) -> int:
        return (
            self.agent_config
            + self.docs_spec
            + self.ci_build
            + self.code_structure
            + self.security_scanning
            + self.deterministic_gates
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "agent_config": self.agent_config,
            "docs_spec": self.docs_spec,
            "ci_build": self.ci_build,
            "code_structure": self.code_structure,
            "security_scanning": self.security_scanning,
            "deterministic_gates": self.deterministic_gates,
            "total": self.total,
        }


def compute_readiness_score(repo_root: str) -> ReadinessScore:
    """Score the repository at *repo_root* across six readiness axes."""
    root = Path(repo_root).resolve()
    score = ReadinessScore(repo_root=str(root))

    score.agent_config = _score_agent_config(root)
    score.docs_spec = _score_docs_spec(root)
    score.ci_build = _score_ci_build(root)
    score.code_structure = _score_code_structure(root)
    score.security_scanning = _score_security_scanning(root)
    score.deterministic_gates = _score_deterministic_gates(root)

    return score


# ---------------------------------------------------------------------------
# Axis scorers
# ---------------------------------------------------------------------------


def _exists(*paths: Path) -> bool:
    return any(p.exists() for p in paths)


def _score_agent_config(root: Path) -> int:
    points = 0
    if (root / "AGENTS.md").exists():
        content = (root / "AGENTS.md").read_text(encoding="utf-8", errors="replace")
        # Base presence
        points += 8
        # Has all HC controls
        if all(f"HC{i}" in content for i in range(1, 7)):
            points += 4
        # Has scope boundary / write allowlist
        if "Write Allowlist" in content or "write allowlist" in content.lower():
            points += 4
        # Has skill references
        if ".agents/skills" in content or "SKILL.md" in content:
            points += 4
    # Overlay present
    if (root / "CLAUDE.md").exists():
        points = min(points + 2, _MAX_AXIS)
    return min(points, _MAX_AXIS)


def _score_docs_spec(root: Path) -> int:
    points = 0
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        md_files = list(docs_dir.glob("*.md"))
        if md_files:
            points += 8
            # Architecture doc present
            if any("architecture" in f.name.lower() for f in md_files):
                points += 6
            # More than one doc
            if len(md_files) > 1:
                points += 4
        # Schemas dir
    if (root / "schemas").is_dir():
        points = min(points + 2, _MAX_AXIS)
    return min(points, _MAX_AXIS)


def _score_ci_build(root: Path) -> int:
    points = 0
    if (root / "Makefile").exists():
        points += 6
    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.is_dir():
        yamls = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        if yamls:
            points += 8
            if len(yamls) > 1:
                points += 4
    if (root / "tox.ini").exists():
        points = min(points + 2, _MAX_AXIS)
    return min(points, _MAX_AXIS)


def _score_code_structure(root: Path) -> int:
    points = 0
    if (root / "src").is_dir():
        points += 6
    if (root / "tests").is_dir():
        points += 6
    if (root / "pyproject.toml").exists():
        points += 4
    if (root / "fixtures").is_dir() or (root / "schemas").is_dir():
        points += 4
    return min(points, _MAX_AXIS)


def _score_security_scanning(root: Path) -> int:
    """Check pyproject.toml for security tool configurations."""
    points = 0
    toml = root / "pyproject.toml"
    if not toml.exists():
        return 0
    try:
        content = toml.read_text(encoding="utf-8")
    except OSError:
        return 0

    tools = {
        "ruff": 4,
        "mypy": 4,
        "bandit": 4,
        "detect-secrets": 4,
        "pip-audit": 4,
    }
    for tool, pts in tools.items():
        if tool in content:
            points += pts
    return min(points, _MAX_AXIS)


def _score_deterministic_gates(root: Path) -> int:
    points = 0
    if (root / "Makefile").exists():
        try:
            content = (root / "Makefile").read_text(encoding="utf-8", errors="replace")
            if "verify" in content:
                points += 8
        except OSError:
            pass
    if (root / ".pre-commit-config.yaml").exists():
        points += 6
    if (root / "tox.ini").exists():
        points += 4
    if (root / ".secrets.baseline").exists():
        points += 2
    return min(points, _MAX_AXIS)
