"""Abstract trace adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from llm_sca_tooling.traces.models import RawTraceArtefact, TraceRunContract


class TraceAdapterBase(ABC):
    adapter_id: str
    language: str

    @abstractmethod
    async def run(
        self,
        contract: TraceRunContract,
        *,
        workspace_root: Path | None = None,
    ) -> tuple[RawTraceArtefact, bool]:
        """Return (artefact, non_reproducing)."""
        raise NotImplementedError
