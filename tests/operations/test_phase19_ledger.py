from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.operations.ledger_delete import LedgerDeletionService
from llm_sca_tooling.operations.ledger_export import LedgerExportService
from llm_sca_tooling.operations.ledger_retention import (
    LedgerRetentionPolicy,
    LedgerRetentionService,
)
from llm_sca_tooling.privacy.export_delete import DELETE_CONFIRMATION
from llm_sca_tooling.privacy.retention_policy import RetentionAction
from llm_sca_tooling.schemas.enums import PolicyAction
from llm_sca_tooling.schemas.provenance import RepoRef
from llm_sca_tooling.storage import initialize_workspace
from llm_sca_tooling.storage.operations import OperationalRecord
from tests.storage.conftest import run_event, run_record


def test_ledger_retention_filters_by_kind() -> None:
    service = LedgerRetentionService(
        LedgerRetentionPolicy(
            ledger_kinds=["policy_decision"], operational_record_days=1
        )
    )
    decisions = service.evaluate_operational_records(
        [
            {
                "record_id": "record:1",
                "kind": "policy_decision",
                "created_ts": "2026-05-01T00:00:00Z",
            },
            {
                "record_id": "record:2",
                "kind": "other",
                "created_ts": "2026-05-01T00:00:00Z",
            },
        ],
        now_ts="2026-05-10T00:00:00Z",
    )
    assert [decision.record_id for decision in decisions] == ["record:1"]
    assert decisions[0].action == RetentionAction.EXPORT


def test_ledger_export_and_delete_controls(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / ".llm-sca")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    registered = workspace.repositories.register_repo(repo_root)
    repo_ref = RepoRef(
        repo_id=registered.repo_id,
        name=registered.name,
        default_branch=registered.default_branch,
    )
    workspace.operations.create_run(run_record(repo_ref))
    workspace.operations.append_run_event("run:demo", run_event(1))
    workspace.operations.record_operational_record(
        OperationalRecord(
            record_id="record:1",
            repo_id=repo_ref.repo_id,
            run_id="run:demo",
            event_id="event:run:demo:1",
            kind="policy_decision",
            policy_action=PolicyAction.DENY,
            payload={"authorization": "placeholder"},
        )
    )
    export_path = tmp_path / "ledger.json"
    result = LedgerExportService(workspace.operations).export_operational_ledger(
        export_path, repo_id=repo_ref.repo_id
    )
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert result.record_count == 1
    assert (
        exported["operational_records"][0]["payload"]["authorization"] == "[REDACTED]"
    )
    deletion = LedgerDeletionService(workspace.conn)
    dry_run = deletion.delete_run("run:demo")
    assert dry_run.dry_run
    rejected = deletion.delete_run("run:demo", dry_run=False)
    assert not rejected.approved
    approved = deletion.delete_run(
        "run:demo", dry_run=False, confirmation=DELETE_CONFIRMATION
    )
    assert approved.approved
    assert workspace.operations.query_runs() == []
    workspace.close()
