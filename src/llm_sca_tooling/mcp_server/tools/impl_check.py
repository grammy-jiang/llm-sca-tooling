"""Phase 14 run_implementation_check MCP tool handler."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import (
    ArtifactKind,
    GraphEdgeType,
    GraphNodeType,
    PermissionMode,
    RedactionStatus,
    SideEffectClass,
)
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import _now_ts
from llm_sca_tooling.workflows.impl_check.report import (
    run_implementation_check as _run_impl_check,
)

_log = logging.getLogger(__name__)

_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "spec": {"type": "string"},
        "repos": {"type": "array", "items": {"type": "string"}},
        "policy": {"type": "object"},
        "null_mode": {"type": "boolean"},
        "run_id": {"type": "string"},
    },
    "required": ["spec"],
    "additionalProperties": False,
}

_CODE_NODE_TYPES = {
    GraphNodeType.FILE,
    GraphNodeType.MODULE,
    GraphNodeType.CLASS,
    GraphNodeType.FUNCTION,
}


def _collect_graph_evidence(
    context: McpRequestContext,
    spec_path: Path | None,
    repo_ids: list[str] | None,
) -> tuple[list[str], list[str], bool]:
    """Return (available_symbol_ids, document_link_ids, graph_is_empty).

    Queries the graph store for:
    - All code node qualified_names across registered repos (symbol grounding)
    - DOCUMENTS edges from the spec DOCUMENT node to code nodes (link grounding)

    graph_is_empty is True when no repos are indexed at all.
    """
    graph = context.workspace.graph
    registry = context.workspace.repositories

    all_repos = registry.list_repos(active_only=True)
    if repo_ids:
        all_repos = [r for r in all_repos if r.repo_id in repo_ids]

    if not all_repos:
        _log.warning("impl_check: no registered repos found; grounding will be empty")
        return [], [], True

    symbol_ids: list[str] = []
    graph_empty = True

    for repo in all_repos:
        for node_type in _CODE_NODE_TYPES:
            nodes = graph.fetch_nodes_by_type(repo.repo_id, node_type)
            for node in nodes:
                graph_empty = False
                if node.qualified_name:
                    symbol_ids.append(node.qualified_name)
                if node.file_path:
                    symbol_ids.append(node.file_path)

    if graph_empty:
        _log.warning(
            "impl_check: graph is empty for repos %s — run graph_build first",
            [r.repo_id for r in all_repos],
        )

    # Collect DOCUMENT_LINK evidence from DOCUMENTS edges on the spec file.
    document_link_ids: list[str] = []
    if spec_path is not None and not graph_empty:
        spec_rel = spec_path.as_posix()
        for repo in all_repos:
            doc_nodes = graph.fetch_nodes_by_type(repo.repo_id, GraphNodeType.DOCUMENT)
            for doc_node in doc_nodes:
                if doc_node.file_path and (
                    doc_node.file_path == spec_rel
                    or spec_rel.endswith(doc_node.file_path)
                ):
                    docs_edges = graph.fetch_edges_by_type(
                        repo.repo_id, GraphEdgeType.DOCUMENTS
                    )
                    linked_ids = {
                        e.target_id
                        for e in docs_edges
                        if e.source_id == doc_node.node_id
                    }
                    if linked_ids:
                        target_nodes = [
                            graph.fetch_node(nid)
                            for nid in linked_ids
                            if graph.fetch_node(nid) is not None
                        ]
                        for tn in target_nodes:
                            if tn is not None:
                                if tn.qualified_name:
                                    document_link_ids.append(tn.qualified_name)
                                if tn.file_path:
                                    document_link_ids.append(tn.file_path)

    return symbol_ids, document_link_ids, graph_empty


class RunImplementationCheckTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_implementation_check",
        description=(
            "Phase 14 implementation-check workflow entrypoint. Runs the seven-stage "
            "DAG (spec ingestion -> clause extraction -> intent graph -> contract "
            "generation -> grounding -> static verdict -> aggregation) and returns an "
            "ImplementationCheckReport with ClauseVerdictMatrix. "
            "Prerequisite: run graph_build for the target repo(s) before invoking this "
            "tool — grounding requires an up-to-date graph index."
        ),
        input_schema=_SCHEMA,
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        spec_raw = args.get("spec")
        if not isinstance(spec_raw, str) or not spec_raw.strip():
            raise ToolInvalidArguments("spec is required")
        # Accept either a file path or inline Markdown text.
        spec_path_arg = Path(spec_raw.strip())
        resolved_spec_path: Path | None = None
        if spec_path_arg.suffix in {".md", ".txt"}:
            candidate = (
                spec_path_arg
                if spec_path_arg.is_absolute()
                else Path.cwd() / spec_path_arg
            )
            if candidate.exists():
                spec = candidate.read_text(encoding="utf-8")
                resolved_spec_path = candidate
            else:
                spec = spec_raw
        else:
            spec = spec_raw

        run_id_raw = args.get("run_id")
        if run_id_raw is not None and not isinstance(run_id_raw, str):
            raise ToolInvalidArguments("run_id must be a string")

        null_mode = bool(args.get("null_mode", True))

        repo_ids_raw = args.get("repos")
        repo_ids: list[str] | None = None
        if isinstance(repo_ids_raw, list):
            repo_ids = [str(r) for r in repo_ids_raw if r]

        # --- Gap fix: query the graph for grounding evidence ---
        available_symbol_ids, document_link_ids, graph_empty = _collect_graph_evidence(
            context, resolved_spec_path, repo_ids
        )
        _log.info(
            "impl_check: graph evidence collected symbols=%d doc_links=%d empty=%s",
            len(available_symbol_ids),
            len(document_link_ids),
            graph_empty,
        )

        # asyncio.run() fails inside FastMCP's event loop; run in a thread instead.
        import concurrent.futures

        coro = _run_impl_check(
            spec=spec,
            run_id=run_id_raw or None,
            null_mode=null_mode,
            available_symbol_ids=available_symbol_ids or None,
            document_link_ids=document_link_ids or None,
        )
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False

        if in_loop:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                report, matrix = pool.submit(asyncio.run, coro).result()
        else:
            report, matrix = asyncio.run(coro)

        report_payload = report.model_dump_json(indent=2)
        digest = hashlib.sha256(report_payload.encode("utf-8")).hexdigest()
        artifact_dir = context.workspace.artifact_root / "impl_check"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"report_{digest[:24]}.json"
        path.write_text(report_payload + "\n", encoding="utf-8")

        ref = ArtifactRef(
            artifact_id=f"art:impl-check-report:{digest[:24]}",
            kind=ArtifactKind.REPORT,
            uri=str(path),
            sha256=digest,
            size_bytes=path.stat().st_size,
            media_type="application/json",
            redaction_status=RedactionStatus.REDACTED,
            created_ts=_now_ts(),
        )
        artifact = context.workspace.artifacts.record_artifact(
            ref, repo_id=None, payload_path=Path(path)
        )

        result_payload: JsonObject = {
            "report": report.model_dump(mode="json"),
            "clause_verdict_matrix": matrix.model_dump(mode="json"),
        }
        if graph_empty:
            result_payload["warning"] = (
                "Graph index was empty; grounding was not possible. "
                "Run graph_build for the target repo(s) first, then re-run "
                "run_implementation_check for accurate verdicts."
            )

        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=result_payload,
            artifact_refs=[artifact],
        )


__all__ = ["RunImplementationCheckTool"]
