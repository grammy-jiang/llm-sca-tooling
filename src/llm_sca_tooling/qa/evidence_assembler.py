"""Assemble evidence citations for repository answers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.qa.blame import BlameEntry
from llm_sca_tooling.qa.confidence import ConfidenceLabel, min_confidence
from llm_sca_tooling.qa.graph_query import DocumentLink, GraphPath
from llm_sca_tooling.qa.interface_lookup import InterfaceContractResult
from llm_sca_tooling.qa.lookup import GraphNodeRef, LookupResult
from llm_sca_tooling.qa.question import QuestionClass
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.provenance import SourceSpan


class EvidenceType(StrEnum):
    FILE_NODE = "file_node"
    SYMBOL_NODE = "symbol_node"
    GRAPH_PATH = "graph_path"
    INTERFACE_CONTRACT = "interface_contract"
    BLAME_ENTRY = "blame_entry"
    DOCUMENT_LINK = "document_link"
    SAST_ALERT = "sast_alert"


class AnswerEvidence(StrictBaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    node_id: str | None = None
    node_type: str | None = None
    file_path: str | None = None
    span: SourceSpan | None = None
    content_snippet: str | None = None
    confidence: ConfidenceLabel
    source: str


class EvidenceAssembler:
    def from_lookup(self, result: LookupResult, *, limit: int = 20) -> list[AnswerEvidence]:
        evidence = []
        for ref in result.matched_nodes[:limit]:
            evidence_type = EvidenceType.FILE_NODE if ref.node_type == "file" else EvidenceType.SYMBOL_NODE
            evidence.append(AnswerEvidence(evidence_id=f"ev:{ref.node_id}", evidence_type=evidence_type, node_id=ref.node_id, node_type=ref.node_type, file_path=ref.file_path, span=ref.span, confidence=ref.confidence, source=ref.source))
        return evidence

    def from_graph_paths(self, paths: list[GraphPath], *, limit: int = 20) -> list[AnswerEvidence]:
        return [AnswerEvidence(evidence_id=f"ev:{path.path_id}", evidence_type=EvidenceType.GRAPH_PATH, node_id=path.start_node_id, confidence=path.confidence, source="graph_path") for path in paths[:limit]]

    def from_interfaces(self, contracts: list[InterfaceContractResult], *, limit: int = 20) -> list[AnswerEvidence]:
        return [AnswerEvidence(evidence_id=f"ev:{contract.plugin_id}:{contract.interface_record.interface_id}", evidence_type=EvidenceType.INTERFACE_CONTRACT, node_id=contract.interface_record.interface_id, confidence=contract.confidence, source=contract.lookup_path) for contract in contracts[:limit]]

    def from_document_links(self, links: list[DocumentLink], *, limit: int = 20) -> list[AnswerEvidence]:
        return [AnswerEvidence(evidence_id=f"ev:{link.doc_node_id}:{link.code_node_id}", evidence_type=EvidenceType.DOCUMENT_LINK, node_id=link.code_node_id, file_path=link.code_file_path, span=link.code_span, confidence=link.confidence, source=link.edge_type) for link in links[:limit]]

    def from_blame_entries(self, entries: list[BlameEntry], file_path: str, *, limit: int = 20) -> list[AnswerEvidence]:
        return [AnswerEvidence(evidence_id=f"ev:blame:{entry.commit_sha}:{entry.start_line}", evidence_type=EvidenceType.BLAME_ENTRY, file_path=file_path, confidence=ConfidenceLabel.HEURISTIC, source="git_blame") for entry in entries[:limit]]

    def derive_confidence(self, question_class: QuestionClass, evidence: list[AnswerEvidence]) -> tuple[ConfidenceLabel, str, str | None]:
        if not evidence:
            return ConfidenceLabel.UNKNOWN, "no evidence was found", "Provide more specific code token in the question."
        weakest = min_confidence([item.confidence for item in evidence])
        if question_class == QuestionClass.BEHAVIOUR_TRACE:
            return ConfidenceLabel.HEURISTIC, "behaviour-trace confidence is capped until the ship gate is met", None
        if question_class == QuestionClass.OTHER:
            return ConfidenceLabel.HEURISTIC, "other questions are best-effort only", None
        return weakest, "confidence is bounded by the weakest cited evidence", None
