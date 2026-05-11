"""Retention policy model for workspace-level data management."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["RetentionPolicy"]


class RetentionPolicy(BaseModel):
    """Workspace-level data retention and privacy configuration.

    Controls which data classes are scanned for PII/secrets, how long
    records are kept, and whether export-before-delete is required.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    data_classes: list[str] = ["run_record", "incident", "budget_event"]
    redaction_rules: dict[str, str] = {}  # field_name -> replacement
    retention_windows: dict[str, int] = {}  # record_type -> days
    export_on_delete: bool = True
    delete_requires_approval: bool = True
    pii_detection_enabled: bool = True
    secret_scan_enabled: bool = True
    opt_out_categories: list[str] = []
