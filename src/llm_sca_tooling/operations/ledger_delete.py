"""Ledger delete tool — retention-policy-compliant deletion with audit trail."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from llm_sca_tooling.operations.ledger_exporter import LedgerExporter
from llm_sca_tooling.operations.ledger_retention import LedgerRetentionPolicy
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["DeleteAuditRecord", "LedgerDeleteTool"]

logger = get_logger(__name__)


class DeleteAuditRecord:
    """Records what was deleted without retaining the deleted content."""

    def __init__(
        self,
        record_type: str,
        count: int,
        approved_by: str | None,
        exported_to: str | None,
    ) -> None:
        self.record_type = record_type
        self.count = count
        self.approved_by = approved_by
        self.exported_to = exported_to
        self.ts = datetime.now(UTC).isoformat()


class LedgerDeleteTool:
    """Execute retention-policy-compliant deletion of ledger records.

    Args:
        policy: The workspace retention policy.
        store: Mutable mapping representing the operational store.
            Records are dicts; must have a ``record_type`` and ``ts`` field.
        exporter: Optional ``LedgerExporter`` used when ``export_on_delete``.
    """

    def __init__(
        self,
        policy: LedgerRetentionPolicy,
        store: list[dict[str, Any]],
        exporter: LedgerExporter | None = None,
    ) -> None:
        self._policy = policy
        self._store = store
        self._exporter = exporter or LedgerExporter()
        self._audit_trail: list[DeleteAuditRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        approved_by: str | None = None,
        dry_run: bool = False,
    ) -> list[DeleteAuditRecord]:
        """Delete all records past their retention window.

        When ``policy.delete_requires_approval`` is ``True`` and
        *approved_by* is ``None`` the call raises ``PermissionError``.

        Returns the audit trail entries for this run.
        """
        if self._policy.delete_requires_approval and approved_by is None:
            raise PermissionError(
                "deletion requires explicit approval (approved_by must be set)"
            )

        now = datetime.now(UTC)
        _retention_map = {
            "run_record": self._policy.run_record_retention_days,
            "incident": self._policy.incident_retention_days,
            "budget_event": self._policy.budget_event_retention_days,
            "monitor_alert": self._policy.monitor_alert_retention_days,
            "promotion_record": self._policy.promotion_record_retention_days,
            "eval_run": self._policy.eval_run_retention_days,
            "artefact": self._policy.artefact_retention_days,
        }

        to_delete: dict[str, list[dict[str, Any]]] = {}
        for record in self._store:
            rtype = record.get("record_type", "unknown")
            retention_days = _retention_map.get(rtype, -1)
            if retention_days < 0:
                continue
            ts_str = record.get("ts") or record.get("created_at") or ""
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                age = now - ts
                if age > timedelta(days=retention_days):
                    to_delete.setdefault(rtype, []).append(record)
            except ValueError:
                continue

        new_audit: list[DeleteAuditRecord] = []
        for rtype, records in to_delete.items():
            exported_to: str | None = None
            if self._policy.export_on_delete and not dry_run:
                import tempfile  # noqa: PLC0415

                with tempfile.NamedTemporaryFile(
                    suffix=".jsonl.gz", delete=False
                ) as _f:
                    out = _f.name
                self._exporter.export(records, out)
                exported_to = out

            if not dry_run:
                for r in records:
                    self._store.remove(r)

            audit = DeleteAuditRecord(
                record_type=rtype,
                count=len(records),
                approved_by=approved_by,
                exported_to=exported_to,
            )
            new_audit.append(audit)
            self._audit_trail.append(audit)
            logger.info(
                "ledger_delete: type=%s count=%d dry_run=%s",
                rtype,
                len(records),
                dry_run,
            )

        return new_audit

    @property
    def audit_trail(self) -> list[DeleteAuditRecord]:
        return list(self._audit_trail)
