"""Memory retrieval interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.memory.models import CoarseHint, FineHint


class RetrieverInterface(ABC):
    @abstractmethod
    def retrieve_coarse(
        self, *, issue_text: str, repo_id: str, phase: str, max_hints: int = 5
    ) -> tuple[list[CoarseHint], list[CoarseHint]]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_fine(
        self,
        *,
        issue_text: str,
        repo_id: str,
        phase: str,
        graph_node_ids: list[str] | None = None,
        max_hints: int = 5,
    ) -> tuple[list[FineHint], list[FineHint]]:
        raise NotImplementedError
