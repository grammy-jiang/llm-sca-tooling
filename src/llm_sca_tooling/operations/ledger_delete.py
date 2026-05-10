"""Approved deletion helper for operational ledger records."""

from __future__ import annotations

from sqlite3 import Connection

from pydantic import Field

from llm_sca_tooling.privacy.export_delete import DELETE_CONFIRMATION
from llm_sca_tooling.schemas.base import StrictBaseModel


class LedgerDeletionResult(StrictBaseModel):
    scope: str = Field(min_length=1)
    dry_run: bool
    approved: bool
    affected_ids: list[str] = Field(default_factory=list)


class LedgerDeletionService:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def delete_run(
        self,
        run_id: str,
        *,
        dry_run: bool = True,
        confirmation: str | None = None,
    ) -> LedgerDeletionResult:
        affected = self._run_affected_ids(run_id)
        approved = dry_run or confirmation == DELETE_CONFIRMATION
        if not dry_run and not approved:
            return LedgerDeletionResult(
                scope=f"run:{run_id}",
                dry_run=dry_run,
                approved=False,
                affected_ids=affected,
            )
        if not dry_run:
            self.conn.execute(
                "DELETE FROM incident_events WHERE event_id IN (SELECT event_id FROM run_events WHERE run_id=?)",
                (run_id,),
            )
            self.conn.execute("DELETE FROM incident_runs WHERE run_id=?", (run_id,))
            self.conn.execute(
                "DELETE FROM operational_records WHERE run_id=?", (run_id,)
            )
            self.conn.execute("DELETE FROM run_events WHERE run_id=?", (run_id,))
            self.conn.execute("DELETE FROM run_repositories WHERE run_id=?", (run_id,))
            self.conn.execute("DELETE FROM run_records WHERE run_id=?", (run_id,))
            self.conn.commit()
        return LedgerDeletionResult(
            scope=f"run:{run_id}",
            dry_run=dry_run,
            approved=approved,
            affected_ids=affected,
        )

    def delete_incident(
        self,
        incident_id: str,
        *,
        dry_run: bool = True,
        confirmation: str | None = None,
    ) -> LedgerDeletionResult:
        affected = [incident_id]
        approved = dry_run or confirmation == DELETE_CONFIRMATION
        if not dry_run and not approved:
            return LedgerDeletionResult(
                scope=f"incident:{incident_id}",
                dry_run=dry_run,
                approved=False,
                affected_ids=affected,
            )
        if not dry_run:
            self.conn.execute(
                "DELETE FROM incident_events WHERE incident_id=?", (incident_id,)
            )
            self.conn.execute(
                "DELETE FROM incident_runs WHERE incident_id=?", (incident_id,)
            )
            self.conn.execute(
                "DELETE FROM operational_records WHERE incident_id=?", (incident_id,)
            )
            self.conn.execute(
                "DELETE FROM incidents WHERE incident_id=?", (incident_id,)
            )
            self.conn.commit()
        return LedgerDeletionResult(
            scope=f"incident:{incident_id}",
            dry_run=dry_run,
            approved=approved,
            affected_ids=affected,
        )

    def _run_affected_ids(self, run_id: str) -> list[str]:
        ids = [run_id]
        ids.extend(
            str(row["event_id"])
            for row in self.conn.execute(
                "SELECT event_id FROM run_events WHERE run_id=? ORDER BY seq", (run_id,)
            )
        )
        ids.extend(
            str(row["record_id"])
            for row in self.conn.execute(
                "SELECT record_id FROM operational_records WHERE run_id=? ORDER BY created_ts",
                (run_id,),
            )
        )
        return ids
