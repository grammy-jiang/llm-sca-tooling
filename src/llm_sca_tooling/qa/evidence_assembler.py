"""Evidence models and assembly helpers for repo-QA answers."""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import model_validator

from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef, LookupResult
from llm_sca_tooling.qa.question import StrictQaModel

__all__ = [
    "AnswerEvidence",
    "EvidenceAssembler",
    "EvidenceType",
    "bounded_snippet",
]


class EvidenceType(str, Enum):
    file_node = "FILE_NODE"
    symbol_node = "SYMBOL_NODE"
    graph_path = "GRAPH_PATH"
    interface_contract = "INTERFACE_CONTRACT"
    blame_entry = "BLAME_ENTRY"
    document_link = "DOCUMENT_LINK"
    sast_alert = "SAST_ALERT"


class AnswerEvidence(StrictQaModel):
    evidence_id: str
    evidence_type: EvidenceType
    node_id: str | None = None
    node_type: str | None = None
    file_path: str | None = None
    span: dict[str, object] | None = None
    content_snippet: str | None = None
    confidence: str
    source: str
    snapshot_id: str | None = None

    @model_validator(mode="after")
    def _snippet_is_bounded(self) -> AnswerEvidence:
        if self.content_snippet and len(self.content_snippet.splitlines()) > 5:
            raise ValueError("content_snippet must be bounded to at most five lines")
        return self


class EvidenceAssembler:
    def from_lookup(self, result: LookupResult) -> list[AnswerEvidence]:
        evidence: list[AnswerEvidence] = []
        for node in result.matched_nodes:
            evidence.append(_node_evidence(node))
        return evidence

    def from_graph_paths(self, paths: list[GraphPath]) -> list[AnswerEvidence]:
        return [
            AnswerEvidence(
                evidence_id=_evidence_id("path", path.path_id),
                evidence_type=EvidenceType.graph_path,
                node_id=path.node_ids[0] if path.node_ids else None,
                confidence=path.confidence,
                source="graph_path",
            )
            for path in paths
        ]

    def from_interface_contracts(
        self, contracts: list[InterfaceContractResult]
    ) -> list[AnswerEvidence]:
        return [
            AnswerEvidence(
                evidence_id=_evidence_id(
                    "interface", contract.interface_record.interface_id
                ),
                evidence_type=EvidenceType.interface_contract,
                node_id=(
                    contract.server_node_refs[0].node_id
                    if contract.server_node_refs
                    else None
                ),
                file_path=(
                    contract.interface_record.definition_files[0]
                    if contract.interface_record.definition_files
                    else None
                ),
                confidence=contract.confidence,
                source=contract.interface_record.plugin_id,
                snapshot_id=next(iter(contract.snapshot_ids.values()), None),
            )
            for contract in contracts
        ]


def _node_evidence(node: GraphNodeRef) -> AnswerEvidence:
    evidence_type = (
        EvidenceType.file_node
        if node.node_type in {"file", "module"}
        else EvidenceType.symbol_node
    )
    return AnswerEvidence(
        evidence_id=_evidence_id("node", node.node_id),
        evidence_type=evidence_type,
        node_id=node.node_id,
        node_type=node.node_type,
        file_path=node.file_path,
        span=node.span,
        confidence=node.confidence,
        source=node.source,
    )


def bounded_snippet(text: str, *, max_lines: int = 5) -> str:
    return "\n".join(text.splitlines()[:max_lines])


def _evidence_id(prefix: str, value: str) -> str:
    return f"ev:{prefix}:{hashlib.sha256(value.encode()).hexdigest()[:16]}"
