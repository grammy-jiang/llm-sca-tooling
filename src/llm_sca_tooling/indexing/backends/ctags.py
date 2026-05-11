"""Universal ctags adapter — optional symbol enricher.

All subprocess calls use asyncio.create_subprocess_exec with argument arrays
(never shell=True) to prevent command injection.  File paths are never
interpolated into shell strings.

Degrades gracefully when ctags is not installed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import orjson

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import SourceSpan
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["CtagsBackend"]

logger = get_logger(__name__)

_BACKEND_ID = "ctags"
_KIND_MAP: dict[str, GraphNodeType] = {
    "function": GraphNodeType.function,
    "class": GraphNodeType.class_,
    "method": GraphNodeType.method,
    "variable": GraphNodeType.variable,
    "member": GraphNodeType.variable,
    "module": GraphNodeType.module,
    "type": GraphNodeType.type_,
}
_SUPPORTED_LANGUAGES = ["python", "javascript", "java", "go", "rust", "c", "c++"]


async def _exec(*args: str, cwd: Path | None = None) -> tuple[bytes, bytes, int]:
    """Run a command with argument array (no shell).  Returns (stdout, stderr, rc)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    rc = proc.returncode if proc.returncode is not None else 1
    return stdout, stderr, rc


class CtagsBackend:
    """Optional ctags adapter that enriches symbol discovery."""

    def __init__(self) -> None:
        self._version: str | None = None

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        return self._version

    def supported_languages(self) -> list[str]:
        return _SUPPORTED_LANGUAGES.copy()

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        version = await self._get_version()
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=version is not None,
            version=version,
            supported_languages=self.supported_languages(),
            supported_node_types=list(_KIND_MAP.keys()),
            requires_binary=True,
        )

    async def _get_version(self) -> str | None:
        try:
            stdout, _, rc = await _exec("ctags", "--version")
            if rc != 0:
                return None
            self._version = stdout.decode(errors="replace").split("\n")[0].strip()
            return self._version
        except Exception:
            return None

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(backend_id=_BACKEND_ID, backend_version=self._version)
        version = await self._get_version()
        if version is None:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="CTAGS_NOT_AVAILABLE",
                    message="ctags binary not found; skipping ctags enrichment",
                    backend_id=_BACKEND_ID,
                )
            )
            result.finish()
            return result

        batch_size = 50
        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            await self._process_batch(batch, context, result)

        result.finish()
        return result

    async def _process_batch(
        self,
        files: list[Path],
        context: IndexingContext,
        result: BackendResult,
    ) -> None:
        file_args = [str(f) for f in files]
        try:
            stdout, _, _ = await asyncio.wait_for(
                _exec(
                    "ctags",
                    "--output-format=json",
                    "--fields=+nKSt",
                    "--extras=+q",
                    "-f",
                    "-",
                    *file_args,
                    cwd=context.repo_root,
                ),
                timeout=context.config.backend_timeout_ms / 1000,
            )
        except TimeoutError:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="CTAGS_TIMEOUT",
                    message="ctags timed out",
                    backend_id=_BACKEND_ID,
                )
            )
            return
        except Exception as exc:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="CTAGS_EXEC_ERROR",
                    message=f"ctags failed: {exc}",
                    backend_id=_BACKEND_ID,
                )
            )
            return

        now = context.snapshot_ref.captured_ts
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                tag = orjson.loads(line)
            except Exception:
                continue

            kind = tag.get("kind", "")
            node_type = _KIND_MAP.get(kind.lower())
            if node_type is None:
                continue

            file_path = tag.get("path", "")
            try:
                rel_path = str(Path(file_path).relative_to(context.repo_root)).replace(
                    "\\", "/"
                )
            except ValueError:
                rel_path = file_path

            line_no = tag.get("line", 1)
            span = SourceSpan(file_path=rel_path, start_line=line_no, end_line=line_no)
            name = tag.get("name", "")
            prov = parser_provenance(
                context.repo_ref,
                context.snapshot_ref,
                _BACKEND_ID,
                file=rel_path,
                span=span,
            )
            node_id = make_node_id(
                context.repo_ref.repo_id, node_type.value, f"{rel_path}::{name}"
            )
            parent_id = make_node_id(context.repo_ref.repo_id, "module", rel_path)

            result.nodes.append(
                GraphNode(
                    node_id=node_id,
                    node_type=node_type,
                    label=name,
                    qualified_name=name,
                    file_path=rel_path,
                    span=span,
                    repo=context.repo_ref,
                    snapshot=context.snapshot_ref,
                    provenance=prov,
                    properties={"ctags_kind": kind},
                    created_ts=now,
                )
            )
            result.edges.append(
                GraphEdge(
                    edge_id=make_edge_id(
                        context.repo_ref.repo_id, "contains", parent_id, node_id
                    ),
                    edge_type=GraphEdgeType.contains,
                    source_id=parent_id,
                    target_id=node_id,
                    repo=context.repo_ref,
                    snapshot=context.snapshot_ref,
                    provenance=prov,
                    created_ts=now,
                )
            )
            result.files_processed += 1
