"""Cross-language traversal engine."""

from __future__ import annotations

from collections import deque

from pydantic import Field

from llm_sca_tooling.plugins.base import TraversalDirection
from llm_sca_tooling.plugins.interface_record import StrictPluginModel
from llm_sca_tooling.plugins.registry import PluginRegistry
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = [
    "AmbiguousCandidate",
    "CrossLanguageTraversalResult",
    "CrossLanguageTraverser",
    "CrossRepoHop",
    "TraversalHop",
]

_CONFIDENCE_ORDER = {"heuristic": 0, "analyser": 1, "parser": 2}


class TraversalHop(StrictPluginModel):
    hop_number: int
    from_node_id: str
    to_node_id: str
    via_interface_id: str
    plugin_id: str
    edge_type: str
    confidence: str
    operation_name: str | None = None
    repo_boundary_crossed: bool = False
    language_boundary_crossed: bool = True


class AmbiguousCandidate(StrictPluginModel):
    hop_number: int
    from_node_id: str
    candidate_node_ids: list[str]
    plugin_id: str
    reason: str
    confidence: str


class CrossRepoHop(StrictPluginModel):
    from_repo_id: str
    to_repo_id: str
    via_interface_id: str
    plugin_id: str


class CrossLanguageTraversalResult(StrictPluginModel):
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
    def __init__(self, registry: PluginRegistry, workspace: WorkspaceStore) -> None:
        self._registry = registry
        self._workspace = workspace

    async def traverse(
        self,
        start_node_id: str,
        *,
        direction: TraversalDirection = TraversalDirection.both,
        max_hops: int = 10,
        plugins: list[str] | None = None,
        min_confidence: str = "heuristic",
    ) -> CrossLanguageTraversalResult:
        selected = [
            plugin
            for plugin in await self._registry.available_plugins()
            if plugins is None or plugin.plugin_id in plugins
        ]
        if not selected:
            return CrossLanguageTraversalResult(
                start_node_id=start_node_id,
                diagnostics=["NO_AVAILABLE_INTERFACE_PLUGINS"],
                termination_reason="no_plugins",
            )
        visited = {start_node_id}
        queue: deque[str] = deque([start_node_id])
        hops: list[TraversalHop] = []
        ambiguous: list[AmbiguousCandidate] = []
        while queue and len(hops) < max_hops:
            current = queue.popleft()
            for plugin in selected:
                for link in await plugin.traverse(current, direction, self._workspace):
                    target = (
                        link.to_node_id
                        if link.from_node_id == current
                        else link.from_node_id
                    )
                    if _CONFIDENCE_ORDER.get(
                        link.confidence, 0
                    ) < _CONFIDENCE_ORDER.get(min_confidence, 0):
                        ambiguous.append(
                            AmbiguousCandidate(
                                hop_number=len(hops) + 1,
                                from_node_id=current,
                                candidate_node_ids=[target],
                                plugin_id=plugin.plugin_id,
                                reason="confidence_cutoff",
                                confidence=link.confidence,
                            )
                        )
                        continue
                    if target in visited:
                        continue
                    visited.add(target)
                    queue.append(target)
                    hops.append(
                        TraversalHop(
                            hop_number=len(hops) + 1,
                            from_node_id=current,
                            to_node_id=target,
                            via_interface_id=link.via_interface_id,
                            plugin_id=plugin.plugin_id,
                            edge_type=link.edge_type,
                            confidence=link.confidence,
                            operation_name=link.operation_name,
                        )
                    )
                    if len(hops) >= max_hops:
                        break
        return CrossLanguageTraversalResult(
            start_node_id=start_node_id,
            hops=hops,
            total_hops=len(hops),
            reached_node_ids=sorted(visited - {start_node_id}),
            terminated_early=bool(queue),
            termination_reason="max_hops" if queue else "no_more_links",
            ambiguous_candidates=ambiguous,
        )
