"""RDS v0.2 feature computation."""

from __future__ import annotations

import re

from llm_sca_tooling.evaluation.benchmark_adapter import GoldPatchRecord
from llm_sca_tooling.evaluation.models import RDSFeatureVector

__all__ = ["compute_rds_features"]


def _files_from_diff(diff: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"^\+\+\+ b/(.+)$", diff, flags=re.MULTILINE)
        if match.group(1).strip() != "/dev/null"
    ]


def compute_rds_features(
    *,
    instance_id: str,
    eval_run_id: str,
    gold_patch: GoldPatchRecord | None = None,
    source_snapshot_id: str | None = None,
) -> RDSFeatureVector:
    diagnostics: dict[str, str] = {}
    changed_files = gold_patch.changed_files if gold_patch else []
    if not changed_files and gold_patch:
        changed_files = _files_from_diff(gold_patch.diff)
    if not changed_files:
        diagnostics["files_touched"] = "unknown: no gold patch files available"

    diagnostics.update(
        {
            "chain_depth": (
                "unknown: graph traversal not available in Phase 10 null mode"
            ),
            "cross_file_dataflow": (
                "unknown: dataflow graph not available in Phase 10 null mode"
            ),
            "ambient_warning_load": "unknown: SARIF snapshot not supplied",
            "test_brittleness": "unknown: perturbation metadata not supplied",
            "memorisation_distance": "null estimate; calibrated=false",
        }
    )
    return RDSFeatureVector(
        instance_id=instance_id,
        eval_run_id=eval_run_id,
        files_touched=len(set(changed_files)) if changed_files else None,
        chain_depth=None,
        cross_file_dataflow=None,
        ambient_warning_load=None,
        test_brittleness=None,
        memorisation_distance=0.5,
        memorisation_calibrated=False,
        diagnostics=diagnostics,
        source_snapshot_id=source_snapshot_id,
    )
