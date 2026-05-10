"""Trace adapter base contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.traces.models import (
    RawTraceArtefact,
    TraceRunContract,
    TraceRunStatus,
)


class AdapterCaptureResult(StrictBaseModel):
    status: TraceRunStatus
    raw_artefact: RawTraceArtefact | None = None
    non_reproducing: bool = False
    wall_ms: int = Field(default=0, ge=0)
    diagnostics: list[JsonObject] = Field(default_factory=list)


class TraceAdapterBase(ABC):
    adapter_id: str
    supported_languages: tuple[str, ...]

    @abstractmethod
    async def capture(
        self,
        *,
        trace_run_id: str,
        contract: TraceRunContract,
        artifact_root: Path,
    ) -> AdapterCaptureResult:
        raise NotImplementedError
