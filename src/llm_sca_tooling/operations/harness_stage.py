"""Harness-stage assessor.

Classifies a repository against the four maturity stages defined in the
architecture document §3.3:

- S0 — Greenfield: empty or minimal repo, no src/ or tests/ yet
- S1 — Walking skeleton: has src/ and basic structure, minimal/no tests, no CI
- S2 — Growing: has src/ + tests/, basic CI or pre-commit, no full security gates
- S3 — Production: full pipeline — src/, tests/, CI/CD, AGENTS.md, security
       scanning, release gates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["HarnessStageReport", "assess_harness_stage"]


@dataclass
class StageSignal:
    name: str
    present: bool
    path: str = ""


@dataclass
class HarnessStageReport:
    repo_root: str
    stage: str  # S0 | S1 | S2 | S3
    signals: list[StageSignal] = field(default_factory=list)
    rationale: str = ""

    @property
    def stage_int(self) -> int:
        mapping = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
        return mapping.get(self.stage, 0)


def assess_harness_stage(repo_root: str) -> HarnessStageReport:
    """Assess the maturity stage of the repository at *repo_root*."""
    root = Path(repo_root).resolve()
    signals = _collect_signals(root)
    stage, rationale = _classify(signals)
    return HarnessStageReport(
        repo_root=str(root),
        stage=stage,
        signals=signals,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Signal collection
# ---------------------------------------------------------------------------


def _has(root: Path, *paths: str) -> bool:
    return any((root / p).exists() for p in paths)


def _collect_signals(root: Path) -> list[StageSignal]:
    def sig(name: str, *paths: str) -> StageSignal:
        for p in paths:
            full = root / p
            if full.exists():
                return StageSignal(name=name, present=True, path=str(full))
        return StageSignal(name=name, present=False)

    return [
        # S1 signals
        sig("src_dir", "src"),
        sig("tests_dir", "tests"),
        sig("makefile", "Makefile", "makefile"),
        sig("pyproject_toml", "pyproject.toml"),
        sig("package_json", "package.json"),
        # S2 signals
        sig("ci_workflow", ".github/workflows"),
        sig("pre_commit_config", ".pre-commit-config.yaml"),
        sig("tox_ini", "tox.ini"),
        # S3 signals
        sig("agents_md", "AGENTS.md"),
        sig("secrets_baseline", ".secrets.baseline"),
        sig("bandit_config", "pyproject.toml"),  # bandit configured in pyproject
        sig("ruff_config", "pyproject.toml"),  # ruff configured in pyproject
        sig("devcontainer", ".devcontainer"),
    ]


def _has_security_scanning(root: Path) -> bool:
    """Return True if pyproject.toml references security tools."""
    toml = root / "pyproject.toml"
    if not toml.exists():
        return False
    try:
        content = toml.read_text(encoding="utf-8")
        tools = ["bandit", "ruff", "mypy", "detect-secrets", "pip-audit"]
        return any(t in content for t in tools)
    except OSError:
        return False


def _has_ci(root: Path) -> bool:
    return (root / ".github" / "workflows").is_dir() or (root / "tox.ini").exists()


def _classify(signals: list[StageSignal]) -> tuple[str, str]:
    by_name = {s.name: s for s in signals}

    def present(name: str) -> bool:
        return by_name.get(name, StageSignal("", False)).present

    has_src = present("src_dir")
    has_tests = present("tests_dir")
    has_makefile = present("makefile")
    has_pyproject = present("pyproject_toml")
    has_ci = (
        present("ci_workflow") or present("tox_ini") or present("pre_commit_config")
    )
    has_agents_md = present("agents_md")

    # S3: full production setup
    if (
        has_src
        and has_tests
        and has_makefile
        and has_pyproject
        and has_ci
        and has_agents_md
    ):
        return (
            "S3",
            "Repository has src/, tests/, Makefile, pyproject.toml, CI, and AGENTS.md;"
            " classified as S3 (production).",
        )

    # S2: growing — src + tests + some CI
    if has_src and has_tests and (has_ci or has_makefile or has_pyproject):
        return (
            "S2",
            "Repository has src/, tests/, and basic build tooling (Makefile/pyproject/"
            "CI); classified as S2 (growing).",
        )

    # S1: walking skeleton — has src but minimal testing
    if has_src or has_makefile or has_pyproject:
        return (
            "S1",
            "Repository has some structure (src/ or build files) but lacks tests or"
            " complete CI; classified as S1 (walking skeleton).",
        )

    return (
        "S0",
        "Repository has no src/, tests/, or build files; classified as S0 (greenfield).",
    )
