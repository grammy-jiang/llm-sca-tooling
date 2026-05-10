"""Large graph chunking."""

from __future__ import annotations

import uuid

from llm_sca_tooling.hardening.models import GraphChunk
from llm_sca_tooling.schemas.base import JsonObject


class GraphChunker:
    def __init__(self, *, max_chunk_nodes: int = 2000) -> None:
        self.max_chunk_nodes = max_chunk_nodes

    def chunk(self, nodes: list[JsonObject]) -> list[GraphChunk]:
        chunks: list[GraphChunk] = []
        for index in range(0, len(nodes), self.max_chunk_nodes):
            group = nodes[index : index + self.max_chunk_nodes]
            prefix = _module_prefix(group)
            chunks.append(
                GraphChunk(
                    chunk_id=f"graph-chunk:{uuid.uuid4().hex}",
                    node_ids=[str(node.get("node_id")) for node in group],
                    module_prefix=prefix,
                )
            )
        return chunks


def _module_prefix(nodes: list[JsonObject]) -> str:
    if not nodes:
        return ""
    paths = [str(node.get("file_path", "")) for node in nodes if node.get("file_path")]
    if not paths:
        return ""
    first = paths[0].split("/", 1)[0]
    return first if all(path.startswith(first) for path in paths) else ""
