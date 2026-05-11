"""Operational store — run records, events, harness conditions, incidents, promotions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import orjson
from sqlalchemy import select

from llm_sca_tooling.storage.errors import RunEventSequenceError, RunNotFoundError
from llm_sca_tooling.storage.ids import new_uuid
from llm_sca_tooling.storage.models import (
    HarnessConditionRow,
    IncidentEventRow,
    IncidentRow,
    IncidentRunRow,
    OperationalRecordRow,
    PromotionRecordRow,
    ReadinessReportRow,
    RunEventRow,
    RunRecordRow,
    RunRepositoryRow,
)
from llm_sca_tooling.storage.sqlite import AsyncSessionFactory
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["OperationalStore", "RunRecordView"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunRecordView:
    run_id: str
    workflow: str
    status: str
    start_ts: str
    end_ts: str | None
    run_event_count: int
    harness_condition_id: str | None
    final_verdict_id: str | None
    events: list[dict[str, Any]]


class OperationalStore:
    """Append-only run evidence store."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Run records
    # ------------------------------------------------------------------

    async def create_run(
        self,
        workflow: str,
        *,
        run_id: str | None = None,
        repo_ids: list[str] | None = None,
        policy_id: str = "unknown",
        permission_profile: str = "read-only",
        toolset_hash: str = "unknown",
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Create a new run record and return its run_id."""
        rid = run_id or new_uuid("run")
        now = _now()
        async with self._session_factory() as session, session.begin():
            row = RunRecordRow(
                run_id=rid,
                workflow=workflow,
                status="running",
                start_ts=now,
                toolset_hash=toolset_hash,
                policy_id=policy_id,
                permission_profile=permission_profile,
                run_event_count=0,
                payload_json=orjson.dumps(payload or {}).decode(),
                created_ts=now,
                updated_ts=now,
            )
            session.add(row)
            for repo_id in repo_ids or []:
                session.add(RunRepositoryRow(run_id=rid, repo_id=repo_id))
        logger.info("Created run %s workflow=%s", rid, workflow)
        return rid

    async def append_run_event(
        self,
        run_id: str,
        event_type: str,
        actor: str,
        stage: str,
        *,
        seq: int | None = None,
        policy_action: str | None = None,
        redaction_status: str = "not_required",
        token_count: int | None = None,
        wall_ms: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Append a run event and return its event_id."""
        async with self._session_factory() as session, session.begin():
            run = await session.get(RunRecordRow, run_id)
            if run is None:
                raise RunNotFoundError(f"Run {run_id!r} not found")

            # Determine next seq
            if seq is None:
                seq = run.run_event_count + 1

            # Check for duplicate seq
            dup_result = await session.execute(
                select(RunEventRow).where(
                    RunEventRow.run_id == run_id, RunEventRow.seq == seq
                )
            )
            if dup_result.scalar_one_or_none() is not None:
                raise RunEventSequenceError(f"Duplicate seq {seq} in run {run_id!r}")

            event_id = new_uuid("evt")
            now = _now()
            event_row = RunEventRow(
                event_id=event_id,
                run_id=run_id,
                seq=seq,
                ts=now,
                type=event_type,
                actor=actor,
                stage=stage,
                policy_action=policy_action,
                redaction_status=redaction_status,
                token_count=token_count,
                wall_ms=wall_ms,
                payload_json=orjson.dumps(payload or {}).decode(),
                created_ts=now,
            )
            session.add(event_row)
            run.run_event_count = seq
            run.updated_ts = now
            session.add(run)

        return event_id

    async def get_run(
        self, run_id: str, *, include_events: bool = False
    ) -> RunRecordView:
        async with self._session_factory() as session:
            run = await session.get(RunRecordRow, run_id)
            if run is None:
                raise RunNotFoundError(f"Run {run_id!r} not found")

            events: list[dict[str, Any]] = []
            if include_events:
                stmt = (
                    select(RunEventRow)
                    .where(RunEventRow.run_id == run_id)
                    .order_by(RunEventRow.seq)
                )
                result = await session.execute(stmt)
                events = [
                    {
                        "event_id": r.event_id,
                        "seq": r.seq,
                        "type": r.type,
                        "actor": r.actor,
                    }
                    for r in result.scalars().all()
                ]

        return RunRecordView(
            run_id=run.run_id,
            workflow=run.workflow,
            status=run.status,
            start_ts=run.start_ts,
            end_ts=run.end_ts,
            run_event_count=run.run_event_count,
            harness_condition_id=run.harness_condition_id,
            final_verdict_id=run.final_verdict_id,
            events=events,
        )

    async def close_run(
        self,
        run_id: str,
        status: str,
        *,
        final_verdict_id: str | None = None,
        end_ts: str | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(RunRecordRow, run_id)
            if run is None:
                raise RunNotFoundError(f"Run {run_id!r} not found")
            run.status = status
            run.end_ts = end_ts or _now()
            run.final_verdict_id = final_verdict_id
            run.updated_ts = _now()
            session.add(run)

    async def list_runs(
        self,
        *,
        repo_id: str | None = None,
        workflow: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[RunRecordView]:
        async with self._session_factory() as session:
            stmt = (
                select(RunRecordRow).order_by(RunRecordRow.start_ts.desc()).limit(limit)
            )
            if workflow:
                stmt = stmt.where(RunRecordRow.workflow == workflow)
            if status:
                stmt = stmt.where(RunRecordRow.status == status)
            if repo_id:
                from llm_sca_tooling.storage.models import RunRepositoryRow as RRR

                subq = select(RRR.run_id).where(RRR.repo_id == repo_id)
                stmt = stmt.where(RunRecordRow.run_id.in_(subq))
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            RunRecordView(
                run_id=r.run_id,
                workflow=r.workflow,
                status=r.status,
                start_ts=r.start_ts,
                end_ts=r.end_ts,
                run_event_count=r.run_event_count,
                harness_condition_id=r.harness_condition_id,
                final_verdict_id=r.final_verdict_id,
                events=[],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Harness conditions
    # ------------------------------------------------------------------

    async def record_harness_condition(
        self,
        harness_condition_id: str,
        run_id: str | None,
        permission_profile: str,
        toolset_hash: str,
        captured_ts: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        async with self._session_factory() as session, session.begin():
            row = HarnessConditionRow(
                harness_condition_id=harness_condition_id,
                run_id=run_id,
                toolset_hash=toolset_hash,
                permission_profile=permission_profile,
                captured_ts=captured_ts,
                payload_json=orjson.dumps(payload or {}).decode(),
            )
            session.add(row)
            if run_id:
                run = await session.get(RunRecordRow, run_id)
                if run:
                    run.harness_condition_id = harness_condition_id
                    run.updated_ts = _now()
                    session.add(run)
        return harness_condition_id

    # ------------------------------------------------------------------
    # Operational records (generic store for all event types)
    # ------------------------------------------------------------------

    async def record_operational(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        repo_id: str | None = None,
        run_id: str | None = None,
        event_id: str | None = None,
        status: str | None = None,
        policy_action: str | None = None,
        severity: str | None = None,
        incident_id: str | None = None,
    ) -> str:
        record_id = new_uuid("rec")
        async with self._session_factory() as session, session.begin():
            row = OperationalRecordRow(
                record_id=record_id,
                repo_id=repo_id,
                run_id=run_id,
                event_id=event_id,
                kind=kind,
                status=status,
                policy_action=policy_action,
                severity=severity,
                incident_id=incident_id,
                payload_json=orjson.dumps(payload).decode(),
                created_ts=_now(),
            )
            session.add(row)
        return record_id

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    async def record_incident(
        self,
        incident_id: str,
        severity: str,
        title: str,
        source_run_ids: list[str],
        source_event_ids: list[str],
        *,
        primary_repo_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        async with self._session_factory() as session:
            async with session.begin():
                row = IncidentRow(
                    incident_id=incident_id,
                    severity=severity,
                    status="open",
                    title=title,
                    primary_repo_id=primary_repo_id,
                    opened_ts=_now(),
                    payload_json=orjson.dumps(payload or {}).decode(),
                )
                session.add(row)
                await session.flush()  # make incident row visible for FK checks on join rows
                for rid in source_run_ids:
                    session.add(IncidentRunRow(incident_id=incident_id, run_id=rid))
                for eid in source_event_ids:
                    session.add(IncidentEventRow(incident_id=incident_id, event_id=eid))
        return incident_id

    async def query_incidents(
        self,
        *,
        repo_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(IncidentRow).order_by(IncidentRow.opened_ts.desc()).limit(limit)
            )
            if status:
                stmt = stmt.where(IncidentRow.status == status)
            if severity:
                stmt = stmt.where(IncidentRow.severity == severity)
            if repo_id:
                stmt = stmt.where(IncidentRow.primary_repo_id == repo_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "incident_id": r.incident_id,
                "severity": r.severity,
                "status": r.status,
                "title": r.title,
                "opened_ts": r.opened_ts,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Promotion records
    # ------------------------------------------------------------------

    async def record_promotion(
        self,
        source_run_id: str,
        target_type: str,
        owner: str,
        lesson_summary: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        promotion_id = new_uuid("promo")
        now = _now()
        async with self._session_factory() as session, session.begin():
            row = PromotionRecordRow(
                promotion_id=promotion_id,
                source_run_id=source_run_id,
                target_type=target_type,
                review_state="pending",
                owner=owner,
                payload_json=orjson.dumps(
                    {"lesson_summary": lesson_summary, **(payload or {})}
                ).decode(),
                created_ts=now,
                updated_ts=now,
            )
            session.add(row)
        return promotion_id

    # ------------------------------------------------------------------
    # Readiness reports
    # ------------------------------------------------------------------

    async def record_readiness_report(
        self,
        readiness_report_id: str,
        repo_id: str,
        stage: str,
        total_score: int,
        payload: dict[str, Any],
    ) -> str:
        async with self._session_factory() as session, session.begin():
            row = ReadinessReportRow(
                readiness_report_id=readiness_report_id,
                repo_id=repo_id,
                stage=stage,
                total_score=total_score,
                threshold_status="unknown",
                no_regression_status="unknown",
                payload_json=orjson.dumps(payload).decode(),
                created_ts=_now(),
            )
            session.add(row)
        return readiness_report_id

    async def query_readiness_reports(
        self, repo_id: str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(ReadinessReportRow)
                .where(ReadinessReportRow.repo_id == repo_id)
                .order_by(ReadinessReportRow.created_ts.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "readiness_report_id": r.readiness_report_id,
                "stage": r.stage,
                "total_score": r.total_score,
                "created_ts": r.created_ts,
            }
            for r in rows
        ]

    async def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        """Return a single incident record by ID, or None if not found."""
        async with self._session_factory() as session:
            row = await session.get(IncidentRow, incident_id)
            if row is None:
                return None
            run_stmt = select(IncidentRunRow).where(
                IncidentRunRow.incident_id == incident_id
            )
            run_result = await session.execute(run_stmt)
            event_stmt = select(IncidentEventRow).where(
                IncidentEventRow.incident_id == incident_id
            )
            event_result = await session.execute(event_stmt)
        return {
            "incident_id": row.incident_id,
            "severity": row.severity,
            "status": row.status,
            "title": row.title,
            "primary_repo_id": row.primary_repo_id,
            "opened_ts": row.opened_ts,
            "closed_ts": row.closed_ts,
            "source_run_ids": [r.run_id for r in run_result.scalars().all()],
            "source_event_ids": [e.event_id for e in event_result.scalars().all()],
            "payload": orjson.loads(row.payload_json) if row.payload_json else {},
        }

    async def get_harness_condition(
        self, harness_condition_id: str
    ) -> dict[str, Any] | None:
        """Return a single harness condition record by ID, or None if not found."""
        async with self._session_factory() as session:
            row = await session.get(HarnessConditionRow, harness_condition_id)
            if row is None:
                return None
        return {
            "harness_condition_id": row.harness_condition_id,
            "run_id": row.run_id,
            "permission_profile": row.permission_profile,
            "toolset_hash": row.toolset_hash,
            "captured_ts": row.captured_ts,
            "payload": orjson.loads(row.payload_json) if row.payload_json else {},
        }

    async def query_ledger(
        self,
        repo_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return the chronological operational ledger for a repository."""
        async with self._session_factory() as session:
            stmt = (
                select(OperationalRecordRow)
                .where(OperationalRecordRow.repo_id == repo_id)
                .order_by(OperationalRecordRow.created_ts.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "record_id": r.record_id,
                "kind": r.kind,
                "status": r.status,
                "policy_action": r.policy_action,
                "severity": r.severity,
                "incident_id": r.incident_id,
                "run_id": r.run_id,
                "created_ts": r.created_ts,
                "payload": orjson.loads(r.payload_json) if r.payload_json else {},
            }
            for r in rows
        ]

    async def get_latest_readiness_report(self, repo_id: str) -> dict[str, Any] | None:
        """Return the most recent readiness report for a repository."""
        async with self._session_factory() as session:
            stmt = (
                select(ReadinessReportRow)
                .where(ReadinessReportRow.repo_id == repo_id)
                .order_by(ReadinessReportRow.created_ts.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if row is None:
                return None
        return {
            "readiness_report_id": row.readiness_report_id,
            "repo_id": row.repo_id,
            "stage": row.stage,
            "total_score": row.total_score,
            "threshold_status": row.threshold_status,
            "no_regression_status": row.no_regression_status,
            "created_ts": row.created_ts,
            "payload": orjson.loads(row.payload_json) if row.payload_json else {},
        }
