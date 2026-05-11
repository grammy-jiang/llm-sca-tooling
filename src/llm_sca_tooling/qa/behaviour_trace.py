"""Behaviour-trace intent extraction and graph traversal."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.plugins.traversal import (
    CrossLanguageTraversalResult,
    CrossLanguageTraverser,
)
from llm_sca_tooling.qa.graph_query import GraphPath
from llm_sca_tooling.qa.lookup import lookup_symbols
from llm_sca_tooling.qa.question import RepoQuestion, StrictQaModel
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["BehaviourTraceResult", "TraceIntent", "trace_behaviour"]


class TraceIntent(StrictQaModel):
    start_symbol: str | None
    target_symbol: str | None = None
    cross_language: bool = False
    max_hops: int = 8


class BehaviourTraceResult(StrictQaModel):
    intent: TraceIntent
    graph_paths: list[GraphPath] = Field(default_factory=list)
    traversal: dict[str, object] | None = None
    confidence: str
    diagnostics: list[str] = Field(default_factory=list)


async def trace_behaviour(
    workspace: WorkspaceStore,
    question: RepoQuestion,
    traverser: CrossLanguageTraverser | None = None,
    *,
    max_hops: int = 8,
) -> BehaviourTraceResult:
    intent = TraceIntent(
        start_symbol=question.code_tokens[0] if question.code_tokens else None,
        target_symbol=(
            question.code_tokens[1] if len(question.code_tokens) > 1 else None
        ),
        cross_language="cross-language" in question.normalized_text
        or "http" in question.normalized_text
        or "idl" in question.normalized_text,
        max_hops=max_hops,
    )
    if intent.start_symbol is None:
        return BehaviourTraceResult(
            intent=intent, confidence="unknown", diagnostics=["NO_START_SYMBOL"]
        )
    start = await lookup_symbols(workspace, question)
    if not start.matched_nodes:
        return BehaviourTraceResult(
            intent=intent, confidence="unknown", diagnostics=["NO_START_NODE"]
        )
    traversal_payload: dict[str, object] | None = None
    if traverser is not None and intent.cross_language:
        result = await traverser.traverse(
            start.matched_nodes[0].node_id, max_hops=max_hops
        )
        traversal_payload = _result_payload(result)
    path = GraphPath(
        path_id=f"trace:{start.matched_nodes[0].node_id}",
        node_ids=[start.matched_nodes[0].node_id],
        confidence="heuristic",
    )
    return BehaviourTraceResult(
        intent=intent,
        graph_paths=[path],
        traversal=traversal_payload,
        confidence="heuristic",
    )


def _result_payload(result: CrossLanguageTraversalResult) -> dict[str, object]:
    return {
        "start_node_id": result.start_node_id,
        "reached_node_ids": result.reached_node_ids,
        "hops": [hop.model_dump(mode="json") for hop in result.hops],
        "terminated_early": result.terminated_early,
    }
