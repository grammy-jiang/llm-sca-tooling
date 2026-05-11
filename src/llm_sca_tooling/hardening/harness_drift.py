"""Harness drift checker.

Classifies each manifest artefact as ``clean``, ``stale``, ``missing``,
``relaxed``, or ``out-of-stage`` against the current stage and the set of
declared hard constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["DriftClass", "HarnessDriftChecker", "HarnessDriftRecord"]

logger = get_logger(__name__)

DriftClass = Literal["clean", "stale", "missing", "relaxed", "out-of-stage"]

Stage = Literal["S0", "S1", "S2", "S3"]

# Required artefacts per stage (cumulative)
_REQUIRED: dict[Stage, list[str]] = {
    "S0": ["AGENTS.md"],
    "S1": ["AGENTS.md", "CLAUDE.md", ".pre-commit-config.yaml"],
    "S2": [
        "AGENTS.md",
        "CLAUDE.md",
        ".pre-commit-config.yaml",
        ".github/workflows/verify.yml",
        ".secrets.baseline",
    ],
    "S3": [
        "AGENTS.md",
        "CLAUDE.md",
        ".pre-commit-config.yaml",
        ".github/workflows/verify.yml",
        ".secrets.baseline",
        ".github/workflows/governance.yml",
    ],
}

# Patterns in file content that indicate a hard-constraint relaxation
_RELAXATION_PATTERNS = [
    "ignore_missing_secrets",
    "skip_hc",
    "disable_hc",
    "no_secrets_scan",
    "allow_all",
]

# Markers indicating the file is up to date
_MANAGED_MARKER = "local-agent-harness:auto"


@dataclass
class HarnessDriftRecord:
    artefact: str
    drift_class: DriftClass
    detail: str = ""


@dataclass
class DriftReport:
    stage: Stage
    records: list[HarnessDriftRecord] = field(default_factory=list)

    @property
    def has_relaxed(self) -> bool:
        return any(r.drift_class == "relaxed" for r in self.records)

    @property
    def has_missing(self) -> bool:
        return any(r.drift_class == "missing" for r in self.records)

    @property
    def is_clean(self) -> bool:
        return all(r.drift_class == "clean" for r in self.records)


class HarnessDriftChecker:
    """Check harness artefacts for drift.

    Args:
        repo_root: Root directory of the repository to check.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        self._root = Path(repo_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, stage: Stage = "S0") -> DriftReport:
        """Return a ``DriftReport`` for *stage*."""
        required = _REQUIRED.get(stage, _REQUIRED["S0"])
        report = DriftReport(stage=stage)

        for artefact in required:
            path = self._root / artefact
            record = self._classify(artefact, path, stage)
            report.records.append(record)
            logger.debug(
                "drift: %s -> %s (%s)", artefact, record.drift_class, record.detail
            )

        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify(self, artefact: str, path: Path, stage: Stage) -> HarnessDriftRecord:
        if not path.exists():
            return HarnessDriftRecord(
                artefact=artefact,
                drift_class="missing",
                detail=f"Required for stage {stage} but not found",
            )

        content = self._read(path)

        # Check for hard-constraint relaxation
        for pattern in _RELAXATION_PATTERNS:
            if pattern in content:
                return HarnessDriftRecord(
                    artefact=artefact,
                    drift_class="relaxed",
                    detail=f"Contains relaxation pattern: {pattern!r}",
                )

        # Check staleness via managed marker
        if artefact == "AGENTS.md" and _MANAGED_MARKER not in content:
            return HarnessDriftRecord(
                artefact=artefact,
                drift_class="stale",
                detail="AGENTS.md missing managed section marker",
            )

        return HarnessDriftRecord(
            artefact=artefact,
            drift_class="clean",
            detail="",
        )

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
