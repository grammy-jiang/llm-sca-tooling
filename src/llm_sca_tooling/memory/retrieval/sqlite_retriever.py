"""Concrete memory retriever wrapping CoarseRetriever and FineRetriever."""

from __future__ import annotations

from llm_sca_tooling.memory.models import CoarseHint, FineHint
from llm_sca_tooling.memory.retrieval.coarse import CoarseRetriever
from llm_sca_tooling.memory.retrieval.fine import FineRetriever
from llm_sca_tooling.memory.retrieval.interface import RetrieverInterface
from llm_sca_tooling.memory.retrieval.misalignment_guard import MisalignmentGuard
from llm_sca_tooling.memory.store import MemoryStore


class SqliteMemoryRetriever(RetrieverInterface):
    """Concrete retriever backed by SQLite via CoarseRetriever and FineRetriever."""

    def __init__(
        self, store: MemoryStore, guard: MisalignmentGuard | None = None
    ) -> None:
        self._coarse = CoarseRetriever(store, guard)
        self._fine = FineRetriever(store, guard)

    def retrieve_coarse(
        self,
        *,
        issue_text: str,
        repo_id: str,
        phase: str,  # noqa: ARG002
        max_hints: int = 5,
    ) -> tuple[list[CoarseHint], list[CoarseHint]]:
        return self._coarse.retrieve(
            issue_text=issue_text, repo_id=repo_id, max_hints=max_hints
        )

    def retrieve_fine(
        self,
        *,
        issue_text: str,
        repo_id: str,
        phase: str,  # noqa: ARG002
        graph_node_ids: list[str] | None = None,
        max_hints: int = 5,
    ) -> tuple[list[FineHint], list[FineHint]]:
        return self._fine.retrieve(
            issue_text=issue_text,
            repo_id=repo_id,
            graph_node_ids=graph_node_ids,
            max_hints=max_hints,
        )


__all__ = ["SqliteMemoryRetriever"]
