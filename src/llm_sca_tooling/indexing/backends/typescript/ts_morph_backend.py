"""Real TypeScript/JavaScript backend driven by ts-morph.

Spawns a vendored Node runner (``runner/index.mjs``) that parses sources with
ts-morph and emits parser-grade facts — including cross-file import and call
edges resolved through ts-morph's symbol/type resolution, which the regex
fallback cannot produce. When Node or the runner dependencies are unavailable
the backend delegates to the heuristic regex backend, so indexing always
degrades gracefully instead of failing.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.backends.typescript.ts_backend import (
    TypeScriptBackend,
    _add_package_evidence,
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

__all__ = ["TsMorphBackend"]

_BACKEND_ID = "typescript.tsmorph"
_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_RUNNER_DIR = Path(__file__).parent / "runner"
_RUNNER_ENTRY = _RUNNER_DIR / "index.mjs"

_KIND_TO_NODE_TYPE = {
    "class": GraphNodeType.class_,
    "interface": GraphNodeType.interface,
    "function": GraphNodeType.function,
    "method": GraphNodeType.function,
    "enum": GraphNodeType.class_,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _node_id(repo_id: str, node_type: GraphNodeType, key: str) -> str:
    return make_node_id(repo_id, node_type.value, key)


class TsMorphBackend:
    """ts-morph-backed TS/JS backend with regex-fallback delegation."""

    def __init__(self) -> None:
        self._fallback = TypeScriptBackend()
        self._resolved_version: str | None = None

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        return self._resolved_version or "ts-morph"

    def supported_languages(self) -> list[str]:
        return ["typescript", "javascript"]

    def is_available(self) -> bool:
        """Node on PATH and the runner's dependencies installed."""
        return (
            shutil.which("node") is not None
            and _RUNNER_ENTRY.is_file()
            and (_RUNNER_DIR / "node_modules" / "ts-morph").is_dir()
        )

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        available = self.is_available()
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=available,
            version=self.backend_version() if available else None,
            supported_languages=self.supported_languages(),
            supported_node_types=[
                GraphNodeType.module.value,
                GraphNodeType.class_.value,
                GraphNodeType.interface.value,
                GraphNodeType.function.value,
            ],
            requires_binary=True,
            limitations=(
                []
                if available
                else ["node/ts-morph unavailable; delegating to regex fallback"]
            ),
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        ts_files = [p for p in files if p.suffix in _EXTENSIONS]
        if not self.is_available() or not ts_files:
            return await self._fallback.index_files(context, files)
        try:
            facts = await self._run_runner(context.repo_root, ts_files)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result = await self._fallback.index_files(context, files)
            result.diagnostics.append(
                IndexingDiagnostic(
                    code="ts_morph_runner_failed",
                    message=f"ts-morph runner failed ({exc}); used regex fallback",
                    severity=DiagnosticSeverity.warning,
                    backend_id=_BACKEND_ID,
                )
            )
            return result
        return self._map_facts(context, facts)

    async def _run_runner(self, repo_root: Path, files: list[Path]) -> dict[str, Any]:
        request = json.dumps(
            {
                "repoRoot": str(repo_root),
                "files": [str(p) for p in files],
            }
        ).encode()
        proc = await asyncio.create_subprocess_exec(
            "node",
            str(_RUNNER_ENTRY),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(request)
        if proc.returncode != 0:
            raise OSError(
                f"node runner exited {proc.returncode}: "
                f"{stderr.decode(errors='replace')[:500]}"
            )
        data: dict[str, Any] = json.loads(stdout.decode())
        return data

    def _map_facts(
        self, context: IndexingContext, facts: dict[str, Any]
    ) -> BackendResult:
        version = str(facts.get("tsMorphVersion") or "ts-morph")
        self._resolved_version = f"ts-morph {version}"
        result = BackendResult(_BACKEND_ID, self.backend_version())
        repo_id = context.repo_ref.repo_id
        # (file, qualified_name) -> node_id, for resolving import/call edges.
        module_ids: dict[str, str] = {}
        symbol_ids: dict[tuple[str, str], str] = {}

        for module in facts.get("modules", []):
            file = str(module["file"])
            module_id = _node_id(repo_id, GraphNodeType.module, file)
            module_ids[file] = module_id
            result.nodes.append(
                self._make_node(
                    context,
                    module_id,
                    GraphNodeType.module,
                    Path(file).stem,
                    file,
                    file,
                    None,
                )
            )
            result.files_processed += 1

        for sym in facts.get("symbols", []):
            file = str(sym["file"])
            qname = str(sym["qualifiedName"])
            node_type = _KIND_TO_NODE_TYPE.get(str(sym["kind"]), GraphNodeType.function)
            node_id = _node_id(repo_id, node_type, f"{file}::{qname}")
            symbol_ids[(file, qname)] = node_id
            span = SourceSpan(
                file_path=file,
                start_line=int(sym["startLine"]),
                end_line=int(sym["endLine"]),
            )
            result.nodes.append(
                self._make_node(
                    context,
                    node_id,
                    node_type,
                    str(sym["name"]),
                    qname,
                    file,
                    span,
                )
            )
            parent_id = module_ids.get(file)
            if parent_id:
                result.edges.append(
                    self._make_edge(
                        context, GraphEdgeType.contains, parent_id, node_id, file
                    )
                )

        for imp in facts.get("imports", []):
            src = module_ids.get(str(imp["from"]))
            tgt = module_ids.get(str(imp["to"]))
            if src and tgt:
                result.edges.append(
                    self._make_edge(
                        context, GraphEdgeType.imports, src, tgt, str(imp["from"])
                    )
                )

        for call in facts.get("calls", []):
            caller = call["from"]
            callee = call["to"]
            src = symbol_ids.get((str(caller["file"]), str(caller["name"])))
            tgt = symbol_ids.get((str(callee["file"]), str(callee["name"])))
            if src and tgt and src != tgt:
                result.edges.append(
                    self._make_edge(
                        context,
                        GraphEdgeType.calls,
                        src,
                        tgt,
                        str(caller["file"]),
                    )
                )

        _add_package_evidence(context, result)
        result.finish()
        return result

    def _make_node(
        self,
        context: IndexingContext,
        node_id: str,
        node_type: GraphNodeType,
        label: str,
        qualified_name: str,
        file_path: str,
        span: SourceSpan | None,
    ) -> GraphNode:
        return GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            qualified_name=qualified_name,
            repo=context.repo_ref,
            snapshot=context.snapshot_ref,
            file_path=file_path,
            span=span,
            # Parser-grade: ts-morph resolves real AST symbols, so these win
            # reconciliation over the heuristic regex backend.
            provenance=parser_provenance(
                context.repo_ref,
                context.snapshot_ref,
                _BACKEND_ID,
                file=file_path,
                span=span,
            ),
            properties={"language": "typescript", "parser": "ts-morph"},
            created_ts=_now(),
        )

    def _make_edge(
        self,
        context: IndexingContext,
        edge_type: GraphEdgeType,
        source_id: str,
        target_id: str,
        file_path: str,
    ) -> GraphEdge:
        return GraphEdge(
            edge_id=make_edge_id(
                context.repo_ref.repo_id, edge_type.value, source_id, target_id
            ),
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            repo=context.repo_ref,
            snapshot=context.snapshot_ref,
            provenance=parser_provenance(
                context.repo_ref,
                context.snapshot_ref,
                _BACKEND_ID,
                file=file_path,
                confidence=0.95,
            ),
            confidence=0.95,
            properties={"agreement": "confirmed", "parser": "ts-morph"},
            created_ts=_now(),
        )
