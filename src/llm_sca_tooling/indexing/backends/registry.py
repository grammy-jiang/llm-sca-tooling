"""Backend capability registry."""

from __future__ import annotations

from typing import Protocol

from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.capability import (
    BackendAvailability,
    BackendCapabilityDescriptor,
)

__all__ = ["BackendRegistry", "Phase5Backend"]


class Phase5Backend(Protocol):
    @property
    def backend_id(self) -> str: ...

    def describe_capabilities(self) -> BackendCapabilityDescriptor: ...

    async def check_availability(
        self, context: IndexingContext | None = None
    ) -> BackendAvailability: ...

    def supported_languages(self) -> list[str]: ...


class BackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, Phase5Backend] = {}

    def register(self, backend: Phase5Backend) -> None:
        if backend.backend_id in self._backends:
            raise ValueError(f"duplicate backend: {backend.backend_id}")
        self._backends[backend.backend_id] = backend

    def list_backends(self) -> list[Phase5Backend]:
        return list(self._backends.values())

    def available_backends(self, language: str) -> list[Phase5Backend]:
        return [
            backend
            for backend in self._backends.values()
            if language in backend.supported_languages()
        ]

    def capability_report(self) -> list[BackendCapabilityDescriptor]:
        return [backend.describe_capabilities() for backend in self._backends.values()]

    async def availability_check(
        self, context: IndexingContext | None = None
    ) -> list[BackendAvailability]:
        return [
            await backend.check_availability(context)
            for backend in self._backends.values()
        ]
