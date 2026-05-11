"""Interface contract lookup over Phase 7 interface records."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.plugins.interface_record import InterfaceRecord
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.qa.lookup import GraphNodeRef
from llm_sca_tooling.qa.question import StrictQaModel
from llm_sca_tooling.storage.graph_queries import GraphQueryStore

__all__ = ["InterfaceContractResult", "lookup_interface_contract"]


class InterfaceContractResult(StrictQaModel):
    interface_record: InterfaceRecord
    matched_operations: list[object] = Field(default_factory=list)
    server_node_refs: list[GraphNodeRef] = Field(default_factory=list)
    client_node_refs: list[GraphNodeRef] = Field(default_factory=list)
    generated_artifact_refs: list[object] = Field(default_factory=list)
    confidence: str = "parser"
    snapshot_ids: dict[str, str] = Field(default_factory=dict)


async def lookup_interface_contract(
    store: InterfaceRecordStore,
    graph: GraphQueryStore,
    *,
    plugin_id: str,
    interface_name: str,
    repo: str | None = None,
    include_operations: bool = True,
    include_node_refs: bool = True,
) -> InterfaceContractResult | None:
    records = await store.list_records(plugin_id=plugin_id)
    for record in records:
        if record.interface_name != interface_name or (
            repo and repo not in record.source_repos
        ):
            continue
        server_ids = [
            node_id
            for operation in record.operations
            for node_id in operation.server_handler_node_ids
        ]
        client_ids = [
            node_id
            for operation in record.operations
            for node_id in operation.client_callsite_node_ids
        ]
        return InterfaceContractResult(
            interface_record=record,
            matched_operations=list(record.operations) if include_operations else [],
            server_node_refs=(
                await _node_refs(graph, server_ids) if include_node_refs else []
            ),
            client_node_refs=(
                await _node_refs(graph, client_ids) if include_node_refs else []
            ),
            generated_artifact_refs=list(record.generated_artifacts),
            snapshot_ids=record.snapshot_ids,
        )
    return None


async def _node_refs(graph: GraphQueryStore, node_ids: list[str]) -> list[GraphNodeRef]:
    refs: list[GraphNodeRef] = []
    for node_id in node_ids:
        node = await graph.fetch_node(node_id)
        if node is None:
            continue
        refs.append(
            GraphNodeRef(
                node_id=node.node_id,
                node_type=node.node_type.value,
                repo_id=node.repo.repo_id,
                file_path=node.file_path,
                span=node.span.model_dump(mode="json") if node.span else None,
                symbol_path=node.qualified_name or node.label,
                confidence=node.provenance.derivation.value,
                source="interface_contract",
            )
        )
    return refs
