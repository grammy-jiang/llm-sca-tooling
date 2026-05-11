"""Ledger retention policy model and enforcement."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["LedgerRetentionPolicy"]


class LedgerRetentionPolicy(BaseModel):
    """Defines how long each ledger record class is retained.

    Retention is expressed in days.  ``-1`` means retain indefinitely.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    run_record_retention_days: int = 90
    incident_retention_days: int = 365
    budget_event_retention_days: int = 30
    monitor_alert_retention_days: int = 30
    promotion_record_retention_days: int = 365
    eval_run_retention_days: int = 90
    artefact_retention_days: int = 90
    export_on_delete: bool = True
    delete_requires_approval: bool = True
