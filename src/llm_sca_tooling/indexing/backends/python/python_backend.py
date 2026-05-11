"""Python backend orchestrator combining AST, pyan3, and Pyright diagnostics."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendResult, IndexingContext
from llm_sca_tooling.indexing.backends.python.pyan3_adapter import Pyan3Adapter
from llm_sca_tooling.indexing.backends.python.pyright_adapter import PyrightAdapter
from llm_sca_tooling.indexing.backends.python_ast import PythonASTBackend
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic

__all__ = ["PythonBackend"]


class PythonBackend:
    @property
    def backend_id(self) -> str:
        return "python"

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        ast_result = await PythonASTBackend().index_files(context, files)
        pyan_result = await Pyan3Adapter().index_files(context, files)
        pyright = await PyrightAdapter().check_availability(context)
        result = BackendResult("python", "phase5")
        result.nodes = [*ast_result.nodes]
        result.edges = [*ast_result.edges, *pyan_result.edges]
        result.diagnostics = [*ast_result.diagnostics, *pyan_result.diagnostics]
        if not pyright.available:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="BACKEND_UNAVAILABLE",
                    message="Pyright unavailable; Python backend running without LSP facts",
                    backend_id="python.pyright",
                    details={
                        "missing_deps": pyright.missing_deps,
                        "warnings": pyright.warnings,
                    },
                )
            )
        result.files_processed = ast_result.files_processed
        result.files_skipped = ast_result.files_skipped
        result.finish()
        return result
