"""Tests for the LedgerRetentionPolicy model."""

from __future__ import annotations

import pytest

from llm_sca_tooling.operations.ledger_retention import LedgerRetentionPolicy


def test_defaults() -> None:
    policy = LedgerRetentionPolicy(workspace_id="ws:001")
    assert policy.run_record_retention_days == 90
    assert policy.incident_retention_days == 365
    assert policy.budget_event_retention_days == 30
    assert policy.monitor_alert_retention_days == 30
    assert policy.promotion_record_retention_days == 365
    assert policy.eval_run_retention_days == 90
    assert policy.artefact_retention_days == 90
    assert policy.export_on_delete is True
    assert policy.delete_requires_approval is True


def test_custom_retention_days() -> None:
    policy = LedgerRetentionPolicy(
        workspace_id="ws:002",
        run_record_retention_days=180,
        incident_retention_days=-1,  # retain indefinitely
    )
    assert policy.run_record_retention_days == 180
    assert policy.incident_retention_days == -1


def test_export_on_delete_flag() -> None:
    policy = LedgerRetentionPolicy(workspace_id="ws:003", export_on_delete=False)
    assert policy.export_on_delete is False


def test_delete_requires_approval_flag() -> None:
    policy = LedgerRetentionPolicy(
        workspace_id="ws:004", delete_requires_approval=False
    )
    assert policy.delete_requires_approval is False


def test_round_trip() -> None:
    policy = LedgerRetentionPolicy(workspace_id="ws:005", artefact_retention_days=180)
    dumped = policy.model_dump_json()
    loaded = LedgerRetentionPolicy.model_validate_json(dumped)
    assert loaded.workspace_id == "ws:005"
    assert loaded.artefact_retention_days == 180


def test_extra_fields_forbidden() -> None:
    with pytest.raises(Exception):
        LedgerRetentionPolicy(workspace_id="ws:006", unknown_field="bad")  # type: ignore[call-arg]
