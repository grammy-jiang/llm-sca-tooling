"""Cross-language traversal engine."""

from __future__ import annotations

from collections import deque

from pydantic import Field

from llm_sca_tooling.plugins.capability import (
    CONFIDENCE_RANK,
    ConfidenceLevel,
    TraversalDirection,
)
from llm_sca_tooling.plugins.registry import PluginRegistry
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.graph_store import GraphStore


class TraversalHop(StrictBaseModel):
    hop_number: int
    from_node_id: str
    to_node_id: str
    via_interface_id: str
    plugin_id: str
    edge_type: str
    confidence: ConfidenceLevel
    operation_name: str | None = None
    repo_boundary_crossed: bool = False
    language_boundary_crossed: bool = False


class AmbiguousCandidate(StrictBaseModel):
    hop_number: int
    from_node_id: str
    candidate_node_ids: list[str]
    plugin_id: str
    reason: str
    confidence: ConfidenceLevel


class CrossRepoHop(StrictBaseModel):
    from_repo_id: str
    to_repo_id: str
    via_interface_id: str
    plugin_id: str


class CrossLanguageTraversalResult(StrictBaseModel):
    start_node_id: str
    hops: list[TraversalHop] = Field(default_factory=list)
    total_hops: int = 0
    reached_node_ids: list[str] = Field(default_factory=list)
    terminated_early: bool = False
    termination_reason: str | None = None
    ambiguous_candidates: list[AmbiguousCandidate] = Field(default_factory=list)
    cross_repo_hops: list[CrossRepoHop] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class CrossLanguageTraverser:
    def __init__(
        self, plugin_registry: PluginRegistry, graph_store: GraphStore
    ) -> None:
        self.plugin_registry = plugin_registry
        self.graph_store = graph_store

    def traverse(
        self,
        start_node_id: str,
        direction: TraversalDirection = TraversalDirection.BOTH,
        max_hops: int = 10,
        plugins: list[str] | None = None,
        min_confidence: ConfidenceLevel | None = None,
    ) -> CrossLanguageTraversalResult:
        result = CrossLanguageTraversalResult(
            start_node_id=start_node_id, reached_node_ids=[start_node_id]
        )
        if max_hops <= 0:
            result.terminated_early = True
            result.termination_reason = "max_hops"
            return result
        selected = (
            [self.plugin_registry.require(plugin_id) for plugin_id in plugins]
            if plugins
            else self.plugin_registry.available_plugins()
        )
        if not selected:
            result.termination_reason = "no_plugins"
            result.diagnostics.append("no_available_interface_plugins")
            return result
        minimum = min_confidence or ConfidenceLevel.HEURISTIC
        visited = {start_node_id}
        queue: deque[str] = deque([start_node_id])
        while queue:
            current = queue.popleft()
            for plugin in selected:
                for link in plugin.traverse(current, direction, self.graph_store):
                    if CONFIDENCE_RANK[link.confidence] < CONFIDENCE_RANK[minimum]:
                        result.ambiguous_candidates.append(
                            AmbiguousCandidate(
                                hop_number=len(result.hops) + 1,
                                from_node_id=current,
                                candidate_node_ids=[link.to_node_id],
                                plugin_id=link.plugin_id,
                                reason="confidence_cutoff",
                                confidence=link.confidence,
                            )
                        )
                        continue
                    if link.to_node_id in visited:
                        continue
                    visited.add(link.to_node_id)
                    queue.append(link.to_node_id)
                    repo_crossed = bool(
                        link.from_repo_id
                        and link.to_repo_id
                        and link.from_repo_id != link.to_repo_id
                    )
                    language_crossed = bool(
                        link.from_language
                        and link.to_language
                        and link.from_language != link.to_language
                    )
                    result.hops.append(
                        TraversalHop(
                            hop_number=len(result.hops) + 1,
                            from_node_id=link.from_node_id,
                            to_node_id=link.to_node_id,
                            via_interface_id=link.via_interface_id,
                            plugin_id=link.plugin_id,
                            edge_type=link.edge_type,
                            confidence=link.confidence,
                            operation_name=link.operation_name,
                            repo_boundary_crossed=repo_crossed,
                            language_boundary_crossed=language_crossed,
                        )
                    )
                    result.reached_node_ids.append(link.to_node_id)
                    if repo_crossed:
                        result.cross_repo_hops.append(
                            CrossRepoHop(
                                from_repo_id=link.from_repo_id or "",
                                to_repo_id=link.to_repo_id or "",
                                via_interface_id=link.via_interface_id,
                                plugin_id=link.plugin_id,
                            )
                        )
                    if len(result.hops) >= max_hops:
                        result.terminated_early = True
                        result.termination_reason = "max_hops"
                        result.total_hops = len(result.hops)
                        return result
        result.termination_reason = "no_more_links"
        result.total_hops = len(result.hops)
        return result
