"""Export and delete metadata pipeline for the right-to-delete path."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_sca_tooling.operations.ledger_exporter import LedgerExporter
from llm_sca_tooling.privacy.retention_policy import RetentionPolicy
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["ExportDeletePipeline", "DeletionRequest"]

logger = get_logger(__name__)


class DeletionRequest:
    def __init__(self, workspace_id: str, requested_by: str) -> None:
        self.workspace_id = workspace_id
        self.requested_by = requested_by
        self.requested_at = datetime.now(UTC).isoformat()
        self.completed_at: str | None = None
        self.exported_to: str | None = None
        self.records_deleted: int = 0


class ExportDeletePipeline:
    """Process workspace-level right-to-delete requests.

    Exports workspace-private records to an archive before deletion.
    The deletion audit trail is retained for 30 days minimum.

    Args:
        policy: Workspace retention policy.
        store: The mutable list of records.
        export_dir: Directory for export archives.
    """

    _AUDIT_RETENTION_DAYS = 30

    def __init__(
        self,
        policy: RetentionPolicy,
        store: list[dict[str, Any]],
        export_dir: str | Path = ".agent/exports",
    ) -> None:
        self._policy = policy
        self._store = store
        self._export_dir = Path(export_dir)
        self._exporter = LedgerExporter()
        self._audit: list[DeletionRequest] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_delete(self, requested_by: str) -> DeletionRequest:
        """Execute a full workspace deletion.

        Shared eval-suite artefacts are not deleted.  All workspace-private
        records are exported (when ``export_on_delete``) then removed.
        """
        req = DeletionRequest(
            workspace_id=self._policy.workspace_id,
            requested_by=requested_by,
        )

        # Filter to workspace-private records only
        private_records = [
            r
            for r in self._store
            if r.get("workspace_id") == self._policy.workspace_id
            and not r.get("shared_eval_artefact", False)
        ]

        if self._policy.export_on_delete and private_records:
            out = (
                self._export_dir
                / f"delete_{self._policy.workspace_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.jsonl.gz"
            )
            self._export_dir.mkdir(parents=True, exist_ok=True)
            self._exporter.export(private_records, out)
            req.exported_to = str(out)

        for r in private_records:
            self._store.remove(r)

        req.records_deleted = len(private_records)
        req.completed_at = datetime.now(UTC).isoformat()
        self._audit.append(req)
        logger.info(
            "right_to_delete: workspace=%s deleted=%d",
            self._policy.workspace_id,
            len(private_records),
        )
        return req

    @property
    def audit_trail(self) -> list[DeletionRequest]:
        return list(self._audit)
