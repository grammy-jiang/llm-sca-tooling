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


def _compute_chain_depth(
    conn: Connection | None,
    instance_id: str,
    gold_patch: GoldPatchRecord,
) -> int | None:
    """Query graph for max call chain depth through touched files."""
    if conn is None:
        return None
    try:
        placeholders = ",".join("?" for _ in gold_patch.touched_files)
        if not gold_patch.touched_files:
            return None
        row = conn.execute(
            "SELECT MAX(depth) AS max_depth FROM graph_edges "
            f"WHERE source_file IN ({placeholders}) "
            f"OR target_file IN ({placeholders})",
            gold_patch.touched_files * 2,
        ).fetchone()
        if row is None:
            return None
        value = row["max_depth"] if hasattr(row, "keys") else row[0]
        return int(value) if value is not None else None
    except Exception:
        return None


def _compute_cross_file_dataflow(
    conn: Connection | None,
    gold_patch: GoldPatchRecord,
) -> int | None:
    """Count cross-file dataflow edges in gold patch files."""
    if conn is None or not gold_patch.touched_files:
        return None
    try:
        placeholders = ",".join("?" for _ in gold_patch.touched_files)
        row = conn.execute(
            "SELECT count(*) AS cnt FROM graph_edges "
            "WHERE edge_type = 'dataflow' "
            f"AND source_file IN ({placeholders}) "
            f"AND target_file NOT IN ({placeholders})",
            gold_patch.touched_files * 2,
        ).fetchone()
        if row is None:
            return 0
        value = row["cnt"] if hasattr(row, "keys") else row[0]
        return int(value) if value is not None else 0
    except Exception:
        return None


def _compute_test_brittleness(
    conn: Connection | None,
    instance_id: str,
) -> float | None:
    """Compute mutation test brittleness from stored metadata."""
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT brittleness FROM instance_metadata WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
        if row is None:
            return None
        value = row["brittleness"] if hasattr(row, "keys") else row[0]
        return float(value) if value is not None else None
    except Exception:
        return None


def _compute_memorisation_distance(
    descriptor: InstanceDescriptor,
) -> tuple[float, bool]:
    """Return (distance, calibrated) based on descriptor metadata."""
    meta = descriptor.metadata or {}
    if "memorisation_distance" in meta:
        raw = meta["memorisation_distance"]
        calibrated = bool(meta.get("memorisation_calibrated", False))
        try:
            return float(raw), calibrated
        except (TypeError, ValueError):
            pass
    return 0.5, False


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
    chain_depth = _compute_chain_depth(conn, descriptor.instance_id, gold_patch)
    if chain_depth is None:
        diagnostics["chain_depth"] = (
            "graph symbol chain data unavailable in Phase 10 null mode"
        )
    cross_file_dataflow = _compute_cross_file_dataflow(conn, gold_patch)
    if cross_file_dataflow is None:
        diagnostics["cross_file_dataflow"] = (
            "cross-file dataflow edges unavailable for fixture instance"
        )
    test_brittleness = _compute_test_brittleness(conn, descriptor.instance_id)
    if test_brittleness is None:
        diagnostics["test_brittleness"] = "mutation metadata unavailable"
    ambient_warning_load = _count_sarif_alerts(conn, gold_patch.touched_files)
    if ambient_warning_load is None:
        diagnostics["ambient_warning_load"] = "SARIF store unavailable"
    memorisation_distance, memorisation_calibrated = _compute_memorisation_distance(
        descriptor
    )
    return RDSFeatureVector(
        instance_id=descriptor.instance_id,
        eval_run_id=eval_run_id,
        files_touched=files_touched,
        chain_depth=chain_depth,
        cross_file_dataflow=cross_file_dataflow,
        ambient_warning_load=ambient_warning_load,
        test_brittleness=test_brittleness,
        memorisation_distance=memorisation_distance,
        memorisation_calibrated=memorisation_calibrated,
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
