"""Tests for ExportDeletePipeline."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.privacy.export_delete import ExportDeletePipeline
from llm_sca_tooling.privacy.retention_policy import RetentionPolicy


def _policy(ws: str = "ws1", **kwargs) -> RetentionPolicy:
    return RetentionPolicy(workspace_id=ws, delete_requires_approval=False, **kwargs)


def test_request_delete_removes_workspace_records(tmp_path: Path) -> None:
    store = [
        {"event_id": "e1", "workspace_id": "ws1", "data": "ok"},
        {"event_id": "e2", "workspace_id": "ws2", "data": "other"},
    ]
    pipeline = ExportDeletePipeline(
        policy=_policy("ws1"), store=store, export_dir=str(tmp_path)
    )
    req = pipeline.request_delete(requested_by="user")
    assert req.records_deleted == 1
    # Only the ws2 record should remain
    assert all(r["workspace_id"] == "ws2" for r in store)


def test_request_delete_audit_records_created(tmp_path: Path) -> None:
    store: list[dict] = []
    pipeline = ExportDeletePipeline(
        policy=_policy(), store=store, export_dir=str(tmp_path)
    )
    pipeline.request_delete(requested_by="user")
    assert len(pipeline.audit_trail) == 1


def test_shared_eval_artefact_not_deleted(tmp_path: Path) -> None:
    store = [
        {"workspace_id": "ws1", "shared_eval_artefact": True, "data": "keep"},
    ]
    pipeline = ExportDeletePipeline(
        policy=_policy("ws1"), store=store, export_dir=str(tmp_path)
    )
    req = pipeline.request_delete(requested_by="user")
    assert req.records_deleted == 0
    assert len(store) == 1


def test_request_delete_exports_before_deleting(tmp_path: Path) -> None:
    store = [{"workspace_id": "ws1", "data": "private"}]
    pipeline = ExportDeletePipeline(
        policy=_policy("ws1", export_on_delete=True),
        store=store,
        export_dir=str(tmp_path),
    )
    req = pipeline.request_delete(requested_by="user")
    assert req.exported_to is not None
