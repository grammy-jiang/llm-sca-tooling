"""ABI-relevant symbol annotations."""

from __future__ import annotations

from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.schemas.graph import GraphNode


class AbiEdgeBuilder:
    def annotate_public_symbols(self, nodes: list[GraphNode]) -> list[GraphNode]:
        annotated = []
        for node in nodes:
            if node.node_type in {GraphNodeType.CLASS, GraphNodeType.FUNCTION, GraphNodeType.METHOD} and not node.label.startswith("_"):
                clone = node.model_copy(deep=True)
                clone.properties = {**clone.properties, "abi_public": True}
                annotated.append(clone)
            else:
                annotated.append(node)
        return annotated
