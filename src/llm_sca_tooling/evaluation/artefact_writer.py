"""Evaluation artifact writing helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm_sca_tooling.evaluation.models import EvalRun
from llm_sca_tooling.indexing.hashing import hash_file
from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class EvaluationArtifactWriter:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def write_eval_run_bundle(self, run: EvalRun) -> EvalRun:
        refs = {
            "instance_results_ref": self.write_json(
                run.eval_run_id,
                "instance_results",
                [item.model_dump(mode="json") for item in run.instance_results],
            ).artifact_id,
            "aggregate_metrics_ref": self.write_json(
                run.eval_run_id,
                "aggregate_metrics",
                (
                    run.aggregate_metrics.model_dump(mode="json")
                    if run.aggregate_metrics
                    else None
                ),
            ).artifact_id,
            "rds_summary_ref": self.write_json(
                run.eval_run_id,
                "rds_summary",
                run.rds_summary or {},
            ).artifact_id,
            "operational_metrics_ref": self.write_json(
                run.eval_run_id,
                "operational_metrics",
                (
                    run.operational_metrics.model_dump(mode="json")
                    if run.operational_metrics
                    else None
                ),
            ).artifact_id,
        }
        manifest_payload = {
            "eval_run_id": run.eval_run_id,
            "artifacts": refs,
            "created_ts": _now_ts(),
        }
        manifest_ref = self.write_json(
            run.eval_run_id, "artifact_manifest", manifest_payload
        )
        updated = run.model_copy(
            update={
                **refs,
                "artefact_manifest_ref": manifest_ref.artifact_id,
                "artifact_manifest": manifest_payload,
            }
        )
        self.write_json(run.eval_run_id, "eval_run", updated.model_dump(mode="json"))
        return updated

    def write_json(self, run_id: str, name: str, payload: Any) -> ArtifactRef:
        root = self.workspace.artifact_root / "eval" / run_id.replace(":", "_")
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{name}.json"
        path.write_text(
            json.dumps(_to_jsonable(payload), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        digest = hash_file(path)
        artifact_id = f"art:eval:{_safe_id(run_id)}:{name}:{digest[:16]}"
        ref = ArtifactRef(
            artifact_id=artifact_id,
            kind=ArtifactKind.REPORT,
            uri=str(path),
            sha256=digest,
            size_bytes=path.stat().st_size,
            media_type="application/json",
            redaction_status=RedactionStatus.REDACTED,
            created_ts=_now_ts(),
        )
        # The shared artifact table's run_id foreign key points at workflow
        # run_records. Eval runs have their own eval_runs table in Phase 10, so
        # eval linkage is kept in the eval artifact manifest instead.
        return self.workspace.artifacts.record_artifact(ref, payload_path=Path(path))


def _safe_id(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:24]


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value
