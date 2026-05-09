"""Interface-contract lookup for repo QA."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.plugins.interface_record import InterfaceOperation, InterfaceRecord
from llm_sca_tooling.plugins.store import InterfaceIndexStore
from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.lookup import GraphNodeRef, node_ref
from llm_sca_tooling.qa.question import RepoQuestion
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.workspace import WorkspaceStore


class InterfaceContractResult(StrictBaseModel):
    interface_record: InterfaceRecord
    plugin_id: str
    interface_name: str
    matched_operations: list[InterfaceOperation] = Field(default_factory=list)
    server_node_refs: list[GraphNodeRef] = Field(default_factory=list)
    client_node_refs: list[GraphNodeRef] = Field(default_factory=list)
    confidence: ConfidenceLabel
    lookup_path: str


class InterfaceContractLookup:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace
        self.store = InterfaceIndexStore(workspace)

    def lookup(
        self, question: RepoQuestion, repo_id: str | None = None
    ) -> list[InterfaceContractResult]:
        results: list[InterfaceContractResult] = []
        records = self.store.list_records(repo_id=repo_id)
        tokens = {
            token.lower()
            for token in question.code_tokens
            + question.file_hints
            + question.normalized_text.split()
        }
        for record in records:
            name_tokens = {
                record.interface_name.lower(),
                record.interface_id.lower(),
                *[path.lower() for path in record.definition_files],
            }
            if tokens & name_tokens or any(
                token in record.interface_name.lower()
                for token in tokens
                if len(token) > 2
            ):
                results.append(self._result(record, "by_name"))
                continue
            if any(path.lower() in tokens for path in record.definition_files):
                results.append(self._result(record, "by_file"))
        return results

    def lookup_record(
        self,
        plugin_id: str,
        interface_name: str,
        *,
        include_operations: bool = True,
        include_node_refs: bool = True,
    ) -> InterfaceContractResult | None:
        record = self.store.get_record(plugin_id, interface_name)
        if record is None:
            return None
        result = self._result(record, "by_name")
        if not include_operations:
            result = result.model_copy(update={"matched_operations": []})
        if not include_node_refs:
            result = result.model_copy(
                update={"server_node_refs": [], "client_node_refs": []}
            )
        return result

    def lookup_by_symbol_ref(self, ref: GraphNodeRef) -> list[InterfaceContractResult]:
        rows = self.workspace.conn.execute(
            "SELECT source_id, target_id FROM graph_edges WHERE (source_id=? OR target_id=?) AND edge_type IN ('exposes','consumes','implements')",
            (ref.node_id, ref.node_id),
        ).fetchall()
        node_ids = {
            row["source_id"] if row["source_id"] != ref.node_id else row["target_id"]
            for row in rows
        }
        results = []
        for record in self.store.list_records(repo_id=ref.repo_id):
            operation_node_ids = {
                node_id
                for operation in record.operations
                for node_id in operation.server_handler_node_ids
                + operation.client_callsite_node_ids
            }
            if node_ids & operation_node_ids:
                results.append(self._result(record, "by_symbol"))
        return results

    def _result(
        self, record: InterfaceRecord, lookup_path: str
    ) -> InterfaceContractResult:
        server_ids = {
            node_id
            for operation in record.operations
            for node_id in operation.server_handler_node_ids
        }
        client_ids = {
            node_id
            for operation in record.operations
            for node_id in operation.client_callsite_node_ids
        }
        return InterfaceContractResult(
            interface_record=record,
            plugin_id=record.plugin_id,
            interface_name=record.interface_name,
            matched_operations=record.operations,
            server_node_refs=self._refs(server_ids, "server_node"),
            client_node_refs=self._refs(client_ids, "client_node"),
            confidence=ConfidenceLabel(
                str(
                    record.confidence.value
                    if hasattr(record.confidence, "value")
                    else record.confidence
                )
            ),
            lookup_path=lookup_path,
        )

    def _refs(self, node_ids: set[str], source: str) -> list[GraphNodeRef]:
        refs = []
        for node_id in node_ids:
            node = self.workspace.graph.fetch_node(node_id)
            if node:
                refs.append(node_ref(node, ConfidenceLabel.PARSER, source))
        return refs
