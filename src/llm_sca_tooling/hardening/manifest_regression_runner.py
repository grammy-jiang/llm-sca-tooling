"""Manifest regression runner for released artefacts.

Loads registered prompts, tool descriptors, and manifest files; compares
them against previously stored snapshots; reports any breaking or
policy-relevant changes.  A regression finding blocks the release gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["ManifestRegressionRunner", "RegressionFinding", "RegressionReport"]

logger = get_logger(__name__)

RegressionClass = Literal[
    "none",
    "visible_behaviour",
    "hidden_policy",
    "tool_order",
    "semantic_mutation",
    "spec_evolution",
    "breaking",
    "policy_relevant",
]


@dataclass
class RegressionFinding:
    artefact_id: str
    classification: RegressionClass
    detail: str
    old_hash: str | None
    new_hash: str


@dataclass
class RegressionReport:
    ts: str
    findings: list[RegressionFinding] = field(default_factory=list)

    @property
    def blocks_release(self) -> bool:
        return any(
            f.classification in ("breaking", "policy_relevant") for f in self.findings
        )

    @property
    def has_changes(self) -> bool:
        return bool(self.findings)


class ManifestRegressionRunner:
    """Compare current artefacts against stored snapshots.

    Args:
        snapshot_store: Path to JSON file storing ``{artefact_id: hash}``.
        artefacts: Mapping of ``{artefact_id: content_str}`` for the
            current release candidates.
    """

    def __init__(
        self,
        snapshot_store: str | Path = ".agent/manifest_snapshots.json",
    ) -> None:
        self._snapshot_path = Path(snapshot_store)
        self._snapshots: dict[str, str] = self._load_snapshots()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, artefacts: dict[str, str]) -> RegressionReport:
        """Compare *artefacts* against stored snapshots.

        Returns a ``RegressionReport`` whose ``blocks_release`` flag is
        ``True`` if any finding is ``breaking`` or ``policy_relevant``.
        """
        report = RegressionReport(ts=datetime.now(UTC).isoformat())

        for artefact_id, content in artefacts.items():
            new_hash = self._hash(content)
            old_hash = self._snapshots.get(artefact_id)

            if old_hash is None:
                # New artefact — not a regression
                logger.info("manifest_regression: new artefact %s", artefact_id)
                continue

            if old_hash == new_hash:
                continue

            classification = self._classify(artefact_id, content)
            report.findings.append(
                RegressionFinding(
                    artefact_id=artefact_id,
                    classification=classification,
                    detail=f"Content hash changed {old_hash[:8]}→{new_hash[:8]}",
                    old_hash=old_hash,
                    new_hash=new_hash,
                )
            )
            logger.warning(
                "manifest_regression: %s changed class=%s",
                artefact_id,
                classification,
            )

        if report.blocks_release:
            logger.error(
                "manifest_regression: BLOCKS RELEASE (%d findings)",
                len(report.findings),
            )
        return report

    def update_snapshots(self, artefacts: dict[str, str]) -> None:
        """Persist current artefact hashes as the new baseline."""
        for artefact_id, content in artefacts.items():
            self._snapshots[artefact_id] = self._hash(content)
        self._save_snapshots()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify(self, artefact_id: str, _content: str) -> RegressionClass:
        """Classify the regression type based on artefact naming conventions."""
        aid = artefact_id.lower()
        if "prompt" in aid:
            return "visible_behaviour"
        if "agents" in aid or "policy" in aid or "hc" in aid:
            return "policy_relevant"
        if "tool" in aid:
            return "tool_order"
        if "skill" in aid:
            return "hidden_policy"
        return "spec_evolution"

    def _load_snapshots(self) -> dict[str, str]:
        if not self._snapshot_path.exists():
            return {}
        try:
            data: Any = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            return dict(data) if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_snapshots(self) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._snapshot_path.write_text(
            json.dumps(self._snapshots, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
