"""Tests for the operational store."""

from __future__ import annotations

import pytest

from llm_sca_tooling.storage import WorkspaceStore
from llm_sca_tooling.storage.errors import RunEventSequenceError, RunNotFoundError


async def test_create_run(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("bug-resolve")
    assert run_id.startswith("run:")


async def test_append_run_event_increments_count(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("test-wf")
    await workspace.operations.append_run_event(
        run_id, "session_start", actor="system", stage="start"
    )
    view = await workspace.operations.get_run(run_id, include_events=True)
    assert view.run_event_count == 1
    assert len(view.events) == 1


async def test_duplicate_event_seq_fails(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    await workspace.operations.append_run_event(
        run_id, "session_start", actor="system", stage="s", seq=1
    )
    with pytest.raises(RunEventSequenceError):
        await workspace.operations.append_run_event(
            run_id, "stage_started", actor="agent", stage="s", seq=1
        )


async def test_close_run(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    await workspace.operations.close_run(run_id, "completed")
    view = await workspace.operations.get_run(run_id)
    assert view.status == "completed"
    assert view.end_ts is not None


async def test_get_run_not_found(workspace: WorkspaceStore) -> None:
    with pytest.raises(RunNotFoundError):
        await workspace.operations.get_run("run:nonexistent")


async def test_harness_condition_links_to_run(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    hcs_id = "hcs:001"
    await workspace.operations.record_harness_condition(
        hcs_id, run_id, "read-only", "hash:xyz", "2026-05-09T00:00:00Z"
    )
    view = await workspace.operations.get_run(run_id)
    assert view.harness_condition_id == hcs_id


async def test_list_runs_by_workflow(workspace: WorkspaceStore) -> None:
    await workspace.operations.create_run("bug-resolve")
    await workspace.operations.create_run("patch-review")
    runs = await workspace.operations.list_runs(workflow="bug-resolve")
    assert all(r.workflow == "bug-resolve" for r in runs)


async def test_list_runs_by_status(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    await workspace.operations.close_run(run_id, "completed")
    runs = await workspace.operations.list_runs(status="completed")
    assert any(r.run_id == run_id for r in runs)


async def test_record_incident(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    evt_id = await workspace.operations.append_run_event(
        run_id, "monitor_alert", actor="system", stage="monitoring"
    )
    inc_id = await workspace.operations.record_incident(
        "inc:001", "P1", "out-of-scope write", [run_id], [evt_id]
    )
    incidents = await workspace.operations.query_incidents(status="open")
    assert any(i["incident_id"] == inc_id for i in incidents)


async def test_readiness_report_stored(workspace: WorkspaceStore, tmp_path) -> None:
    repo = await workspace.registry.register_repo(tmp_path)
    await workspace.operations.record_readiness_report(
        "rr:001", repo.repo_id, "S2", 11, {"total_score": 11}
    )
    reports = await workspace.operations.query_readiness_reports(repo.repo_id)
    assert reports[0]["readiness_report_id"] == "rr:001"


async def test_promotion_candidate_stored(workspace: WorkspaceStore) -> None:
    run_id = await workspace.operations.create_run("wf")
    promo_id = await workspace.operations.record_promotion(
        run_id, "memory", "alice", "Learned to check deps before registering"
    )
    assert promo_id.startswith("promo:")
