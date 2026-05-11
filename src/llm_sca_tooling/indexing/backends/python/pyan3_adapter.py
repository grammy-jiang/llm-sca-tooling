"""pyan3 availability and call-edge adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.backends.capability import BackendAvailability
from llm_sca_tooling.indexing.backends.python_ast import PythonASTBackend
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic

__all__ = ["Pyan3Adapter"]


class Pyan3Adapter:
    @property
    def backend_id(self) -> str:
        return "python.pyan3"

    def backend_version(self) -> str:
        return "phase5-adapter"

    async def check_availability(
        self, context: IndexingContext | None = None
    ) -> BackendAvailability:
        cli = shutil.which("pyan3")
        return BackendAvailability(
            backend_id=self.backend_id,
            available=True,
            tool_path=cli,
            tool_version=self.backend_version(),
            warnings=[] if cli else ["pyan3 CLI unavailable; using AST call fallback"],
        )

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=self.backend_id,
            installed=True,
            version=self.backend_version(),
            supported_languages=["python"],
            supported_node_types=["function", "method"],
            limitations=[
                "falls back to Python AST call extraction when pyan3 CLI is unavailable"
            ],
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = await PythonASTBackend().index_files(context, files)
        result.backend_id = self.backend_id
        result.backend_version = self.backend_version()
        result.edges = [
            edge for edge in result.edges if edge.edge_type.value == "calls"
        ]
        result.nodes = []
        if not result.edges:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="CALL_TARGET_UNRESOLVED",
                    message="pyan3 fallback found no statically resolved call edges",
                    backend_id=self.backend_id,
                )
            )
        return result
