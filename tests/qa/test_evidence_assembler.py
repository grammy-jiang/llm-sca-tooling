"""Tests for EvidenceAssembler."""

from __future__ import annotations

from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.evidence_assembler import (
    AnswerEvidence,
    EvidenceAssembler,
    EvidenceType,
)
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.lookup import GraphNodeRef, LookupResult
from llm_sca_tooling.qa.question import QuestionClass


def _node_ref(
    node_id: str, node_type: str, file_path: str | None = None
) -> GraphNodeRef:
    return GraphNodeRef(
        node_id=node_id,
        node_type=node_type,
        file_path=file_path,
        confidence=ConfidenceLabel.PARSER,
        source="test",
    )


def _lookup_result(
    nodes: list[GraphNodeRef], qclass: QuestionClass = QuestionClass.FILE_LOC
) -> LookupResult:
    return LookupResult(
        question_class=qclass,
        matched_nodes=nodes,
        lookup_strategy="exact_path",
        confidence=ConfidenceLabel.PARSER,
    )


def _graph_path(path_id: str) -> GraphPath:
    return GraphPath(
        path_id=path_id,
        nodes=[],
        edges=[],
        start_node_id="node:start",
        end_node_id="node:end",
        hop_count=0,
        confidence=ConfidenceLabel.ANALYSER,
    )


def test_evidence_assembler_initializes() -> None:
    assembler = EvidenceAssembler()
    assert hasattr(assembler, "from_lookup")
    assert hasattr(assembler, "from_graph_paths")


def test_from_lookup_file_node_produces_file_node_evidence() -> None:
    assembler = EvidenceAssembler()
    ref = _node_ref("node:file:src/core.py", "file", "src/core.py")
    result = assembler.from_lookup(_lookup_result([ref]))

    assert len(result) == 1
    assert result[0].evidence_type == EvidenceType.FILE_NODE
    assert result[0].node_id == "node:file:src/core.py"
    assert result[0].file_path == "src/core.py"


def test_from_lookup_symbol_node_produces_symbol_evidence() -> None:
    assembler = EvidenceAssembler()
    ref = _node_ref("node:func:core.foo", "function", "src/core.py")
    result = assembler.from_lookup(_lookup_result([ref], QuestionClass.SYMBOL_LOC))

    assert len(result) == 1
    assert result[0].evidence_type == EvidenceType.SYMBOL_NODE


def test_from_lookup_empty_returns_empty() -> None:
    assembler = EvidenceAssembler()
    result = assembler.from_lookup(_lookup_result([]))
    assert result == []


def test_from_graph_paths_produces_graph_path_evidence() -> None:
    assembler = EvidenceAssembler()
    paths = [_graph_path("path:abc"), _graph_path("path:def")]
    result = assembler.from_graph_paths(paths)

    assert len(result) == 2
    assert all(ev.evidence_type == EvidenceType.GRAPH_PATH for ev in result)


def test_derive_confidence_no_evidence_returns_unknown() -> None:
    assembler = EvidenceAssembler()
    label, reason, hint = assembler.derive_confidence(QuestionClass.FILE_LOC, [])
    assert label == ConfidenceLabel.UNKNOWN
    assert "no evidence" in reason.lower()
    assert hint is not None


def test_derive_confidence_with_evidence_returns_weakest() -> None:
    assembler = EvidenceAssembler()
    evidence = [
        AnswerEvidence(
            evidence_id="ev:1",
            evidence_type=EvidenceType.FILE_NODE,
            confidence=ConfidenceLabel.HEURISTIC,
            source="test",
        )
    ]
    label, reason, _ = assembler.derive_confidence(QuestionClass.FILE_LOC, evidence)
    assert label == ConfidenceLabel.HEURISTIC


def test_from_lookup_respects_limit() -> None:
    assembler = EvidenceAssembler()
    refs = [_node_ref(f"node:file:{i}", "file", f"src/f{i}.py") for i in range(30)]
    result = assembler.from_lookup(_lookup_result(refs), limit=5)
    assert len(result) == 5
