"""Trajectory write-path validation gates."""

from __future__ import annotations

from typing import Protocol

from llm_sca_tooling.memory.models import (
    MemoryOptInPolicy,
    ReviewState,
    TrajectoryRecord,
    WritePathResult,
)
from llm_sca_tooling.memory.redaction import contains_secret
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.storage.workspace import _now_ts

FORBIDDEN_SNIPPET_PREFIXES = (
    "raw_prompt:",
    "full_trace:",
    "full_source:",
    "command_output:",
)


class _GraphFetch(Protocol):
    def fetch_node(self, node_id: str) -> object | None: ...


def write_trajectory(
    *,
    store: MemoryStore,
    policy: MemoryOptInPolicy,
    trajectory: TrajectoryRecord,
    graph: _GraphFetch | None = None,
) -> WritePathResult:
    failures: list[str] = []
    diagnostics: list[dict[str, object]] = []
    if not policy.enabled:
        failures.append("MemoryDisabled:workspace_disabled")
    elif not policy.repo_enabled(trajectory.repo_id):
        failures.append("MemoryDisabled:repo_disabled")
    if not trajectory.source_run_id:
        failures.append("missing_source_run_id")
    if not trajectory.graph_snapshot_id:
        failures.append("missing_graph_snapshot_id")
    if not trajectory.repo_id:
        failures.append("missing_repo_id")
    if _forbidden_snippet_ids(trajectory.bounded_snippet_ids):
        failures.append("forbidden_raw_memory_reference")
    secret_detected = contains_secret(trajectory.model_dump(mode="json"))
    if secret_detected:
        failures.append("SecretDetected")
    contradiction, detail = _contradiction(trajectory, graph)
    if contradiction:
        diagnostics.append(
            {
                "code": "contradiction_detected",
                "detail": detail,
                "contradiction_check_ts": _now_ts(),
            }
        )
    written = not failures
    stored = trajectory.model_copy(update={"review_state": ReviewState.UNREVIEWED})
    if written:
        store.put_trajectory(stored)
    return WritePathResult(
        trajectory_id=trajectory.trajectory_id,
        gates_passed=written,
        gate_failures=failures,
        secret_detected=secret_detected,
        contradiction_detected=contradiction,
        contradiction_detail=detail,
        review_state_set=ReviewState.UNREVIEWED,
        written=written,
        diagnostics=diagnostics,
    )


def _forbidden_snippet_ids(values: list[str]) -> bool:
    return any(value.startswith(FORBIDDEN_SNIPPET_PREFIXES) for value in values)


def _contradiction(
    trajectory: TrajectoryRecord, graph: _GraphFetch | None
) -> tuple[bool, str]:
    if any(node_id.startswith("missing:") for node_id in trajectory.graph_node_ids):
        return True, "graph_node_id marked missing"
    if graph is None:
        return False, ""
    missing = [
        node_id
        for node_id in trajectory.graph_node_ids
        if graph.fetch_node(node_id) is None
    ]
    if missing:
        return True, f"missing graph nodes: {', '.join(missing)}"
    return False, ""
