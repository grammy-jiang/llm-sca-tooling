"""Graph binding for trace divergence points."""

from __future__ import annotations

from typing import Protocol

from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.traces.models import DivergencePoint


class _GraphLookup(Protocol):
    def find_symbols(
        self,
        repo_id: str,
        qualified_name: str | None = None,
        file_path: str | None = None,
        snapshot_id: str | None = None,
    ) -> list[GraphNode]: ...


def bind_divergence_points(
    points: list[DivergencePoint],
    *,
    graph: _GraphLookup | None,
    repo_id: str | None,
    snapshot_id: str | None = None,
) -> list[DivergencePoint]:
    if graph is None or not repo_id:
        return points
    bound: list[DivergencePoint] = []
    for point in points:
        matches = graph.find_symbols(
            repo_id,
            qualified_name=point.function_path,
            file_path=point.file_path or None,
            snapshot_id=snapshot_id,
        )
        if not matches and point.file_path:
            matches = graph.find_symbols(
                repo_id, file_path=point.file_path, snapshot_id=snapshot_id
            )
        if matches:
            point = point.model_copy(update={"graph_node_id": matches[0].node_id})
        bound.append(point)
    return bound
