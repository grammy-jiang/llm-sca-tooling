"""Language backend registry."""

from __future__ import annotations

from collections import defaultdict

from llm_sca_tooling.indexing.backends.base import BackendAvailability, BackendBase, BackendCapabilityDescriptor


class BackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, BackendBase] = {}
        self._by_language: dict[str, list[str]] = defaultdict(list)

    def register(self, backend: BackendBase) -> None:
        if backend.backend_id in self._backends:
            raise ValueError(f"duplicate backend: {backend.backend_id}")
        self._backends[backend.backend_id] = backend
        for language in backend.describe_capabilities().languages:
            self._by_language[language].append(backend.backend_id)

    def available_backends(self, language: str) -> list[BackendBase]:
        return [
            self._backends[backend_id]
            for backend_id in self._by_language.get(language, [])
            if self._backends[backend_id].check_availability().available
        ]

    def capability_report(self) -> list[BackendCapabilityDescriptor]:
        return [self._backends[backend_id].describe_capabilities() for backend_id in sorted(self._backends)]

    def availability_check(self) -> list[BackendAvailability]:
        return [self._backends[backend_id].check_availability() for backend_id in sorted(self._backends)]
