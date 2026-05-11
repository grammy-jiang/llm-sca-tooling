"""RGFL-style deterministic reasoning scaffold."""

from __future__ import annotations

from llm_sca_tooling.fl.models import CandidateFile, CandidateSymbol, ContextFileEntry

__all__ = ["reason_for_candidate", "symbol_candidates"]


def reason_for_candidate(candidate: CandidateFile, context: ContextFileEntry) -> str:
    signal_text = "; ".join(signal.evidence for signal in candidate.signals)
    graph_count = len(context.graph_slice.get("nodes", []))
    return (
        f"Signals link {candidate.file_path}: {signal_text}. "
        f"Graph/static context includes {graph_count} node(s)."
    )


def symbol_candidates(
    candidates: list[CandidateFile], contexts: list[ContextFileEntry]
) -> list[CandidateSymbol]:
    by_file = {entry.candidate_file.file_path: entry for entry in contexts}
    symbols: list[CandidateSymbol] = []
    for candidate in candidates:
        context = by_file.get(candidate.file_path)
        if context is None:
            continue
        symbol_nodes = [
            node
            for node in context.graph_slice.get("nodes", [])
            if node.get("node_type") in {"function", "method", "class"}
        ]
        if not symbol_nodes:
            symbol_nodes = [
                {
                    "node_id": candidate.node_id,
                    "label": candidate.file_path,
                    "node_type": "file",
                }
            ]
        for node in symbol_nodes[:5]:
            symbols.append(
                CandidateSymbol(
                    candidate_id=f"{candidate.candidate_id}:symbol:{len(symbols)}",
                    symbol_node_id=str(node["node_id"]),
                    symbol_path=str(node.get("qualified_name") or node.get("label")),
                    symbol_type=str(node.get("node_type")),
                    file_path=candidate.file_path,
                    repo_id=candidate.repo_id,
                    signals=candidate.signals,
                    combined_score=candidate.combined_score,
                    confidence=candidate.confidence,
                    reasoning_chain=reason_for_candidate(candidate, context),
                )
            )
    return symbols
