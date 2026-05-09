"""Natural-language behaviour tracing over graph paths."""

from __future__ import annotations

import re

from pydantic import Field

from llm_sca_tooling.plugins.capability import TraversalDirection
from llm_sca_tooling.plugins.registry import default_plugin_registry
from llm_sca_tooling.plugins.traversal import CrossLanguageTraverser
from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.graph_query import GraphPath, GraphPathBuilder
from llm_sca_tooling.qa.lookup import SymbolLocLookup
from llm_sca_tooling.qa.question import RepoQuestion
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.storage.graph_store import GraphStore


BEHAVIOUR_UNCERTAINTY = "Behaviour-tracing accuracy has not yet met the >=70% ship-gate. This answer is supporting evidence only and must not be used as a definitive verdict."


class BehaviourIntent(StrictBaseModel):
    trigger_tokens: list[str] = Field(default_factory=list)
    target_tokens: list[str] = Field(default_factory=list)
    scope_tokens: list[str] = Field(default_factory=list)
    direction: str = "forward"


class TraversalPlan(StrictBaseModel):
    start_node_ids: list[str] = Field(default_factory=list)
    end_node_ids: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)
    max_hops: int = 8
    cross_language: bool = False


class BehaviourTraceResult(StrictBaseModel):
    intent: BehaviourIntent
    plan: TraversalPlan
    graph_paths: list[GraphPath] = Field(default_factory=list)
    confidence: ConfidenceLabel = ConfidenceLabel.UNKNOWN
    unknown_reason: str | None = None
    uncertainty: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class BehaviourTraceEngine:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph = graph_store

    def trace(self, question: RepoQuestion, repo_ids: list[str], *, max_hops: int = 8, behaviour_gate_met: bool = False) -> BehaviourTraceResult:
        intent = extract_intent(question)
        if not intent.trigger_tokens:
            return BehaviourTraceResult(intent=intent, plan=TraversalPlan(max_hops=max_hops), unknown_reason="no_trigger_tokens", confidence=ConfidenceLabel.UNKNOWN)
        lookup_question = question.model_copy(update={"code_tokens": intent.trigger_tokens + question.code_tokens})
        starts = SymbolLocLookup(self.graph).lookup(lookup_question, repo_ids)
        if not starts.matched_nodes:
            return BehaviourTraceResult(intent=intent, plan=TraversalPlan(max_hops=max_hops), unknown_reason="no_start_node_resolved", confidence=ConfidenceLabel.UNKNOWN)
        cross_language = any(token.lower() in {"api", "http", "endpoint", "websocket", "idl", "service", "c++", "python"} for token in intent.scope_tokens + intent.target_tokens + intent.trigger_tokens)
        edge_types = [GraphEdgeType.CALLS.value, GraphEdgeType.DATAFLOW.value, GraphEdgeType.IMPORTS.value, GraphEdgeType.EXPOSES.value, GraphEdgeType.CONSUMES.value, GraphEdgeType.FFI.value]
        plan = TraversalPlan(start_node_ids=[ref.node_id for ref in starts.matched_nodes], edge_types=edge_types, max_hops=max_hops, cross_language=cross_language)
        paths: list[GraphPath] = []
        builder = GraphPathBuilder(self.graph)
        diagnostics: list[str] = []
        for start_id in plan.start_node_ids:
            paths.extend(builder.build_path(start_id, edge_types=edge_types, max_depth=max_hops)[:5])
            if cross_language:
                trace = CrossLanguageTraverser(default_plugin_registry(), self.graph).traverse(start_id, direction=TraversalDirection.BOTH, max_hops=max_hops)
                diagnostics.extend(trace.diagnostics)
                for reached in trace.reached_node_ids:
                    if reached != start_id:
                        paths.extend(builder.build_path(start_id, end_node_id=reached, edge_types=edge_types, max_depth=max_hops)[:1])
        if not paths:
            return BehaviourTraceResult(intent=intent, plan=plan, unknown_reason="no_path_found", confidence=ConfidenceLabel.UNKNOWN, diagnostics=diagnostics)
        return BehaviourTraceResult(intent=intent, plan=plan, graph_paths=paths[:10], confidence=ConfidenceLabel.PARSER if behaviour_gate_met else ConfidenceLabel.HEURISTIC, uncertainty=None if behaviour_gate_met else BEHAVIOUR_UNCERTAINTY, diagnostics=diagnostics)


def extract_intent(question: RepoQuestion) -> BehaviourIntent:
    text = question.normalized_text
    direction = "bidirectional" if "between" in text else "backward" if "caller" in text or "called by" in text else "forward"
    token_source = question.code_tokens or re.findall(r"[A-Za-z_][A-Za-z0-9_.-]*", text)
    stop = {"what", "happens", "when", "how", "does", "work", "trace", "flow", "the", "a", "an", "request", "user", "submits", "if"}
    tokens = [token for token in token_source if token.lower() not in stop]
    trigger_tokens = tokens[:3]
    target_tokens = tokens[3:6]
    scope_tokens = [word for word in ("api", "http", "endpoint", "websocket", "idl", "service", "database", "cross-language") if word in text.lower()]
    return BehaviourIntent(trigger_tokens=trigger_tokens, target_tokens=target_tokens, scope_tokens=scope_tokens, direction=direction)
