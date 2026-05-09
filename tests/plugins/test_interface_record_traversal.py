from __future__ import annotations

from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.plugins.capability import (
    ConfidenceLevel,
    InterfaceKind,
    OperationType,
)
from llm_sca_tooling.plugins.interface_record import (
    InterfaceOperation,
    InterfaceRecord,
    interface_id_for,
    operation_id_for,
)
from llm_sca_tooling.schemas.enums import IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


def test_interface_record_round_trips() -> None:
    repo = RepoRef(repo_id="repo:test")
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        worktree_snapshot_id="snapshot:test",
        dirty=True,
        index_status=IndexStatus.FRESH,
        captured_ts=_now_ts(),
    )
    interface_id = interface_id_for(
        "http-rest", InterfaceKind.HTTP, "GET /users/{id}", repo.repo_id
    )
    operation = InterfaceOperation(
        operation_id=operation_id_for(interface_id, "/users/{id}", "GET"),
        interface_id=interface_id,
        name="/users/{id}",
        operation_type=OperationType.ROUTE,
        http_method="GET",
        path_pattern="/users/{id}",
        confidence=ConfidenceLevel.PARSER,
        binding_method="openapi",
    )
    record = InterfaceRecord(
        interface_id=interface_id,
        kind=InterfaceKind.HTTP,
        plugin_id="http-rest",
        plugin_version="0.1.0",
        interface_name="GET /users/{id}",
        source_repos=[repo.repo_id],
        operations=[operation],
        snapshot_ids={repo.repo_id: "snapshot:test"},
        provenance=make_provenance(
            source_tool="http-rest", repo=repo, snapshot=snapshot
        ),
    )
    assert (
        InterfaceRecord.model_validate_json(record.model_dump_json())
        .operations[0]
        .path_pattern
        == "/users/{id}"
    )
