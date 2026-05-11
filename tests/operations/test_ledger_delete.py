"""Tests for LedgerDeleteTool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from llm_sca_tooling.operations.ledger_delete import LedgerDeleteTool
from llm_sca_tooling.operations.ledger_retention import LedgerRetentionPolicy


def _old_ts(days: int = 400) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _policy(**kwargs) -> LedgerRetentionPolicy:
    return LedgerRetentionPolicy(workspace_id="ws1", **kwargs)


def test_delete_removes_expired_records() -> None:
    store = [
        {"record_type": "run_record", "ts": _old_ts(400)},
        {"record_type": "run_record", "ts": _old_ts(400)},
    ]
    policy = _policy(run_record_retention_days=90, delete_requires_approval=False)
    tool = LedgerDeleteTool(policy=policy, store=store)
    audit = tool.run(approved_by="human")
    total_deleted = sum(a.count for a in audit)
    assert total_deleted == 2
    assert len(store) == 0


def test_delete_without_approval_raises() -> None:
    import pytest

    policy = _policy(delete_requires_approval=True)
    tool = LedgerDeleteTool(policy=policy, store=[])
    with pytest.raises(PermissionError):
        tool.run(approved_by=None)


def test_dry_run_does_not_remove_records() -> None:
    store = [{"record_type": "run_record", "ts": _old_ts(400)}]
    policy = _policy(run_record_retention_days=90, delete_requires_approval=False)
    tool = LedgerDeleteTool(policy=policy, store=store)
    tool.run(approved_by="human", dry_run=True)
    assert len(store) == 1


def test_audit_trail_recorded() -> None:
    store = [{"record_type": "run_record", "ts": _old_ts(400)}]
    policy = _policy(run_record_retention_days=90, delete_requires_approval=False)
    tool = LedgerDeleteTool(policy=policy, store=store)
    tool.run(approved_by="human")
    assert len(tool.audit_trail) == 1
