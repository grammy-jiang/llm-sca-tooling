"""RDS v0.2 feature computation."""

from __future__ import annotations

import json
from sqlite3 import Connection

from llm_sca_tooling.evaluation.benchmark_adapter import (
    GoldPatchRecord,
    InstanceDescriptor,
    IssueRecord,
)
from llm_sca_tooling.evaluation.models import RDSFeatureVector

RDS_AXES = (
    "files_touched",
    "chain_depth",
    "cross_file_dataflow",
    "ambient_warning_load",
    "test_brittleness",
    "memorisation_distance",
)


def compute_rds_features(
    *,
    eval_run_id: str,
    descriptor: InstanceDescriptor,
    issue: IssueRecord,
    gold_patch: GoldPatchRecord,
    conn: Connection | None = None,
    source_snapshot_id: str | None = None,
) -> RDSFeatureVector:
    del issue
    diagnostics: dict[str, str] = {}
    files_touched = len(set(gold_patch.touched_files))
    diagnostics["chain_depth"] = (
        "graph symbol chain data unavailable in Phase 10 null mode"
    )
    diagnostics["cross_file_dataflow"] = (
        "cross-file dataflow edges unavailable for fixture instance"
    )
    diagnostics["test_brittleness"] = "mutation metadata unavailable"
    ambient_warning_load = _count_sarif_alerts(conn, gold_patch.touched_files)
    if ambient_warning_load is None:
        diagnostics["ambient_warning_load"] = "SARIF store unavailable"
    return RDSFeatureVector(
        instance_id=descriptor.instance_id,
        eval_run_id=eval_run_id,
        files_touched=files_touched,
        chain_depth=None,
        cross_file_dataflow=None,
        ambient_warning_load=ambient_warning_load,
        test_brittleness=None,
        memorisation_distance=0.5,
        memorisation_calibrated=False,
        source_snapshot_id=source_snapshot_id,
        provenance={
            "suite_id": descriptor.suite_id,
            "gold_patch_ref": descriptor.gold_patch_ref,
            "rds_version": "0.2",
        },
        diagnostics=diagnostics,
    )


def summarise_rds_features(vectors: list[RDSFeatureVector]) -> dict[str, object]:
    unknown_counts = {
        axis: sum(1 for vector in vectors if getattr(vector, axis) is None)
        for axis in RDS_AXES
    }
    files = [
        vector.files_touched for vector in vectors if vector.files_touched is not None
    ]
    return {
        "rds_version": "0.2",
        "instance_count": len(vectors),
        "unknown_counts": unknown_counts,
        "average_files_touched": (sum(files) / len(files)) if files else None,
        "memorisation_calibrated": all(
            vector.memorisation_calibrated for vector in vectors
        ),
    }


def _count_sarif_alerts(conn: Connection | None, files: list[str]) -> int | None:
    if conn is None or not files:
        return None if conn is None else 0
    placeholders = ",".join("?" for _ in files)
    try:
        row = conn.execute(
            "SELECT count(*) AS count FROM sarif_alerts "
            f"WHERE file_path IN ({placeholders})",
            files,
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return 0
    value = row["count"] if hasattr(row, "keys") else row[0]
    return int(value)


def rds_vector_from_json(payload: str) -> RDSFeatureVector:
    return RDSFeatureVector.model_validate(json.loads(payload))
