"""IndexingService — orchestrates the full graph_build and graph_update flows."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import orjson

from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.cpp import CppBackend
from llm_sca_tooling.indexing.backends.ctags import CtagsBackend
from llm_sca_tooling.indexing.backends.markdown import MarkdownBackend
from llm_sca_tooling.indexing.backends.python.pyan3_adapter import Pyan3Adapter
from llm_sca_tooling.indexing.backends.python_ast import PythonASTBackend
from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.indexing.backends.typescript import TypeScriptBackend
from llm_sca_tooling.indexing.blame import BlameChain, BlameCollector
from llm_sca_tooling.indexing.build_evidence import BuildEvidenceDetector
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.git_metadata import GitMetadataCollector
from llm_sca_tooling.indexing.manifests import GraphManifestGenerator
from llm_sca_tooling.indexing.pipeline import GraphPipeline
from llm_sca_tooling.indexing.result import IndexingResult
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.indexing.snapshots import capture_snapshot
from llm_sca_tooling.indexing.summaries import SummaryCache
from llm_sca_tooling.schemas.provenance import RepoRef
from llm_sca_tooling.storage.workspace import WorkspaceStore
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["IndexingService"]

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class IndexingService:
    """Orchestrate full and incremental graph indexing for registered repositories."""

    def __init__(
        self,
        workspace: WorkspaceStore,
        config: IndexingConfig | None = None,
    ) -> None:
        self._workspace = workspace
        self._config = config or IndexingConfig()
        self._scanner = FileScanner(self._config)
        self._git_collector = GitMetadataCollector()
        self._pipeline = GraphPipeline()
        self._manifest_gen = GraphManifestGenerator()
        self._build_evidence = BuildEvidenceDetector()
        self._blame = BlameCollector()
        self._summaries = SummaryCache()

    async def graph_build(self, repo_path: Path) -> IndexingResult:
        """Full deterministic index build for *repo_path*.

        Steps:
        1. Resolve or register repository.
        2. Create indexing run record.
        3. Capture git metadata and snapshot.
        4. Scan files.
        5. Run Python AST backend.
        6. Run ctags backend (optional enricher).
        7. Run tree-sitter backend (optional enricher).
        8. Detect build/test evidence.
        9. Merge/deduplicate graph facts.
        10. Write through Phase 2 graph store.
        11. Generate graph manifest.
        12. Close run with final status.
        """
        repo_path = repo_path.resolve()

        # Step 1: register or resolve repo
        repo_record = await self._workspace.registry.register_repo(repo_path)
        repo_id = repo_record.repo_id

        # Step 2: create run record
        run_id = await self._workspace.operations.create_run(
            "graph-build",
            repo_ids=[repo_id],
        )

        result = IndexingResult(
            repo_id=repo_id,
            run_id=run_id,
            snapshot_id="unknown",
            status="unknown",
        )

        try:
            await self._do_build(repo_path, repo_id, run_id, result)
        except Exception as exc:
            logger.error("graph_build failed: %s", exc, exc_info=True)
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.error,
                    code="BUILD_FATAL_ERROR",
                    message=f"Build failed: {exc}",
                )
            )
            result.finish("failed")
            await self._workspace.operations.close_run(run_id, "failed")

        return result

    async def _do_build(
        self,
        repo_path: Path,
        repo_id: str,
        run_id: str,
        result: IndexingResult,
    ) -> None:
        # Step 3: git metadata + snapshot
        git_meta = await self._git_collector.collect(repo_path)
        result.diagnostics.extend(git_meta.diagnostics)

        storage_snap, schema_snap = await capture_snapshot(
            self._workspace.snapshots,
            _make_repo_ref(repo_id, repo_path),
            git_meta,
            repo_path,
        )
        result.snapshot_id = storage_snap.snapshot_id

        await self._workspace.registry.set_latest_snapshot(
            repo_id, storage_snap.snapshot_id
        )
        await self._workspace.registry.update_status(repo_id, "indexing")

        await self._workspace.operations.append_run_event(
            run_id,
            "stage_started",
            actor="agent",
            stage="scanning",
            payload={"snapshot_id": storage_snap.snapshot_id},
        )

        # Step 4: scan files

        repo_ref = _make_repo_ref(repo_id, repo_path)
        scan_result = self._scanner.scan(repo_path, repo_ref, schema_snap)
        result.diagnostics.extend(scan_result.diagnostics)
        result.files_scanned = scan_result.files_scanned
        result.files_skipped = scan_result.files_skipped

        await self._workspace.operations.append_run_event(
            run_id,
            "stage_completed",
            actor="agent",
            stage="scanning",
            payload={
                "files_scanned": result.files_scanned,
                "files_skipped": result.files_skipped,
            },
        )

        # Collect files for language backends
        source_files = [
            repo_path / n.file_path
            for n in scan_result.nodes
            if n.file_path and (repo_path / n.file_path).exists()
        ]
        py_files = [path for path in source_files if path.suffix == ".py"]
        ts_files = [
            path
            for path in source_files
            if path.suffix in {".ts", ".tsx", ".js", ".jsx"}
        ]
        cpp_files = [
            path
            for path in source_files
            if path.suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh"}
        ]
        md_files = [
            path for path in source_files if path.suffix.lower() in {".md", ".markdown"}
        ]

        context = IndexingContext(
            repo_root=repo_path,
            repo_ref=repo_ref,
            snapshot_ref=schema_snap,
            config=self._config,
            run_id=run_id,
        )

        # Steps 5-7: run backends
        backend_results = []

        # Python AST (always available)
        py_backend = PythonASTBackend()
        py_result = await py_backend.index_files(context, py_files)
        backend_results.append(py_result)
        result.backend_versions["python_ast"] = (
            py_backend.backend_version() or "unknown"
        )

        pyan_backend = Pyan3Adapter()
        pyan_result = await pyan_backend.index_files(context, py_files)
        backend_results.append(pyan_result)
        result.backend_versions["python_pyan3"] = pyan_backend.backend_version()
        result.diagnostics.extend(pyan_result.diagnostics)

        await self._workspace.operations.append_run_event(
            run_id,
            "stage_completed",
            actor="tool",
            stage="backend:python_ast",
            payload={
                "nodes": len(py_result.nodes),
                "edges": len(py_result.edges),
                "files_processed": py_result.files_processed,
            },
        )

        # ctags (optional)
        ctags_backend = CtagsBackend()
        ctags_caps = await ctags_backend.detect_capabilities(context, source_files)
        if ctags_caps.installed:
            ctags_result = await ctags_backend.index_files(context, source_files)
            backend_results.append(ctags_result)
            result.backend_versions["ctags"] = ctags_caps.version or "unknown"
            result.diagnostics.extend(ctags_result.diagnostics)
        else:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="CTAGS_NOT_AVAILABLE",
                    message="ctags binary not found; ctags enrichment skipped",
                    backend_id="ctags",
                )
            )

        # tree-sitter (optional)
        ts_backend = TreeSitterBackend()
        ts_caps = await ts_backend.detect_capabilities(context, py_files)
        if ts_caps.installed:
            ts_result = await ts_backend.index_files(context, py_files)
            backend_results.append(ts_result)
            result.backend_versions["tree_sitter"] = ts_caps.version or "unknown"
            result.diagnostics.extend(ts_result.diagnostics)
        else:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="TREE_SITTER_NOT_AVAILABLE",
                    message="tree-sitter grammar unavailable; syntax enrichment skipped",
                    backend_id="tree_sitter",
                )
            )

        if ts_files:
            typescript_backend = TypeScriptBackend()
            ts_lang_result = await typescript_backend.index_files(context, ts_files)
            backend_results.append(ts_lang_result)
            result.backend_versions["typescript"] = typescript_backend.backend_version()
            result.diagnostics.extend(ts_lang_result.diagnostics)

        if cpp_files:
            cpp_backend = CppBackend()
            cpp_result = await cpp_backend.index_files(context, cpp_files)
            backend_results.append(cpp_result)
            result.backend_versions["cpp"] = cpp_backend.backend_version()
            result.diagnostics.extend(cpp_result.diagnostics)

        if md_files:
            md_backend = MarkdownBackend()
            md_result = await md_backend.index_files(context, md_files)
            backend_results.append(md_result)
            result.backend_versions["markdown"] = (
                md_backend.backend_version() or "unknown"
            )
            result.diagnostics.extend(md_result.diagnostics)

        # Step 8: build/test evidence
        build_ev = self._build_evidence.detect(repo_path, repo_ref, schema_snap)

        # Step 9: merge
        all_nodes = scan_result.nodes[:]
        all_edges = scan_result.edges[:]
        all_nodes.extend(build_ev.nodes)

        # Create a dummy BackendResult from scanner + build_evidence for merging
        from llm_sca_tooling.indexing.backends.base import BackendResult

        scanner_br = BackendResult(backend_id="scanner", backend_version=None)
        scanner_br.nodes = all_nodes
        scanner_br.edges = all_edges

        merge_result = self._pipeline.merge([scanner_br] + backend_results)
        result.diagnostics.extend(merge_result.diagnostics)

        # Step 9b: collect blame as optional auditable artifacts.
        for path in source_files:
            rel_path = str(path.relative_to(repo_path)).replace("\\", "/")
            chain = await self._blame.collect(
                repo_path,
                rel_path,
                repo_id,
                storage_snap.snapshot_id,
                git_sha=git_meta.git_sha,
                worktree_snapshot_id=storage_snap.worktree_snapshot_id,
            )
            result.diagnostics.extend(chain.diagnostics)
            artifact_id = await self._record_blame_artifact(
                repo_path, chain, repo_id, run_id, storage_snap.snapshot_id
            )
            result.artifact_refs.append(artifact_id)

        # Step 10: write to store
        write_result = await self._workspace.graph.add_nodes(merge_result.nodes)
        result.nodes_added = write_result.written

        edge_result = await self._workspace.graph.add_edges(merge_result.edges)
        result.edges_added = edge_result.written
        result.files_indexed = sum(r.files_processed for r in backend_results)

        await self._workspace.operations.append_run_event(
            run_id,
            "stage_completed",
            actor="agent",
            stage="writing",
            payload={
                "nodes_written": result.nodes_added,
                "edges_written": result.edges_added,
            },
        )

        # Step 11: manifest
        manifest_dir = repo_path / ".llm-sca" / "manifests" / storage_snap.snapshot_id
        manifest = self._manifest_gen.generate(
            merge_result.nodes,
            merge_result.edges,
            repo_id=repo_id,
            snapshot_id=storage_snap.snapshot_id,
            run_id=run_id,
            output_dir=manifest_dir,
            config=self._config,
        )
        result.graph_manifest_id = manifest.manifest_id

        # Mark snapshot fresh or partial
        has_incomplete_evidence = bool(result.errors or result.warnings)
        final_status = "partial" if has_incomplete_evidence else "fresh"
        await self._workspace.snapshots.mark_snapshot_status(
            storage_snap.snapshot_id, final_status
        )
        await self._workspace.registry.update_status(repo_id, final_status)

        result.finish(final_status)
        await self._workspace.operations.close_run(run_id, "completed")
        logger.info(
            "graph_build complete: repo=%s snap=%s nodes=%d edges=%d status=%s",
            repo_id,
            storage_snap.snapshot_id,
            result.nodes_added,
            result.edges_added,
            final_status,
        )

    async def graph_update(self, repo_path: Path) -> IndexingResult:
        """Incremental update — re-index only changed files."""
        repo_path = repo_path.resolve()
        repo_record = await self._workspace.registry.register_repo(repo_path)
        repo_id = repo_record.repo_id

        run_id = await self._workspace.operations.create_run(
            "graph-update",
            repo_ids=[repo_id],
        )

        git_meta = await self._git_collector.collect(repo_path)
        storage_snap, schema_snap = await capture_snapshot(
            self._workspace.snapshots,
            _make_repo_ref(repo_id, repo_path),
            git_meta,
            repo_path,
        )

        result = IndexingResult(
            repo_id=repo_id,
            run_id=run_id,
            snapshot_id=storage_snap.snapshot_id,
            status="unknown",
        )
        result.diagnostics.extend(git_meta.diagnostics)

        changed_files = sorted(set(git_meta.changed_files + git_meta.untracked_files))
        if not changed_files and not git_meta.dirty:
            # No changes detected — full rebuild is safe but wasteful; just report
            result.finish("fresh")
            await self._workspace.operations.close_run(run_id, "completed")
            return result

        await self._workspace.operations.append_run_event(
            run_id,
            "stage_started",
            actor="agent",
            stage="update",
            payload={"changed_files": changed_files},
        )

        repo_ref = _make_repo_ref(repo_id, repo_path)
        context = IndexingContext(
            repo_root=repo_path,
            repo_ref=repo_ref,
            snapshot_ref=schema_snap,
            config=self._config,
            run_id=run_id,
        )

        existing_files = [
            repo_path / rel for rel in changed_files if (repo_path / rel).is_file()
        ]
        deleted_files = [rel for rel in changed_files if not (repo_path / rel).exists()]
        for rel in deleted_files:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="UPDATE_DELETED_FILE",
                    message=f"Changed file no longer exists: {rel}",
                    file_path=rel,
                )
            )
            result.stale_summary_count += self._summaries.invalidate_for_file(
                repo_id, rel
            )

        scan_result = self._scanner.scan(repo_path, repo_ref, schema_snap)
        result.diagnostics.extend(scan_result.diagnostics)
        changed_set = {
            str(path.relative_to(repo_path)).replace("\\", "/")
            for path in existing_files
        }
        changed_nodes = [
            node for node in scan_result.nodes if node.file_path in changed_set
        ]
        changed_node_ids = {node.node_id for node in changed_nodes}
        changed_edges = [
            edge
            for edge in scan_result.edges
            if edge.source_id in changed_node_ids or edge.target_id in changed_node_ids
        ]

        py_files = [path for path in existing_files if path.suffix == ".py"]
        ts_files = [
            path
            for path in existing_files
            if path.suffix in {".ts", ".tsx", ".js", ".jsx"}
        ]
        cpp_files = [
            path
            for path in existing_files
            if path.suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh"}
        ]
        md_files = [
            path
            for path in existing_files
            if path.suffix.lower() in {".md", ".markdown"}
        ]
        py_backend = PythonASTBackend()
        py_result = await py_backend.index_files(context, py_files)
        result.backend_versions["python_ast"] = (
            py_backend.backend_version() or "unknown"
        )
        result.diagnostics.extend(py_result.diagnostics)
        backend_results = [py_result]
        if py_files:
            pyan_result = await Pyan3Adapter().index_files(context, py_files)
            backend_results.append(pyan_result)
            result.diagnostics.extend(pyan_result.diagnostics)
        if ts_files:
            ts_result = await TypeScriptBackend().index_files(context, ts_files)
            backend_results.append(ts_result)
            result.backend_versions["typescript"] = "phase5-python-fallback"
            result.diagnostics.extend(ts_result.diagnostics)
        if cpp_files:
            cpp_result = await CppBackend().index_files(context, cpp_files)
            backend_results.append(cpp_result)
            result.backend_versions["cpp"] = "phase5-python-fallback"
            result.diagnostics.extend(cpp_result.diagnostics)
        if md_files:
            md_backend = MarkdownBackend()
            md_result = await md_backend.index_files(context, md_files)
            backend_results.append(md_result)
            result.backend_versions["markdown"] = (
                md_backend.backend_version() or "unknown"
            )
            result.diagnostics.extend(md_result.diagnostics)

        for rel in changed_set:
            result.stale_summary_count += self._summaries.invalidate_for_file(
                repo_id, rel
            )

        from llm_sca_tooling.indexing.backends.base import BackendResult

        scanner_br = BackendResult(backend_id="scanner", backend_version=None)
        scanner_br.nodes = changed_nodes
        scanner_br.edges = changed_edges

        merge_result = self._pipeline.merge([scanner_br, *backend_results])
        result.diagnostics.extend(merge_result.diagnostics)
        node_result = await self._workspace.graph.add_nodes(merge_result.nodes)
        edge_result = await self._workspace.graph.add_edges(merge_result.edges)
        result.nodes_added = node_result.written
        result.edges_added = edge_result.written
        result.files_scanned = len(existing_files)
        result.files_indexed = sum(r.files_processed for r in backend_results)
        result.files_skipped = sum(r.files_skipped for r in backend_results) + len(
            deleted_files
        )

        manifest_dir = repo_path / ".llm-sca" / "manifests" / storage_snap.snapshot_id
        manifest = self._manifest_gen.generate(
            merge_result.nodes,
            merge_result.edges,
            repo_id=repo_id,
            snapshot_id=storage_snap.snapshot_id,
            run_id=run_id,
            output_dir=manifest_dir,
            config=self._config,
        )
        result.graph_manifest_id = manifest.manifest_id

        final_status = "partial" if result.errors or result.warnings else "fresh"
        await self._workspace.snapshots.mark_snapshot_status(
            storage_snap.snapshot_id, final_status
        )
        await self._workspace.registry.set_latest_snapshot(
            repo_id, storage_snap.snapshot_id
        )
        await self._workspace.registry.update_status(repo_id, final_status)
        await self._workspace.operations.append_run_event(
            run_id,
            "stage_completed",
            actor="agent",
            stage="update",
            payload={
                "files_scanned": result.files_scanned,
                "nodes_written": result.nodes_added,
                "edges_written": result.edges_added,
                "summaries_invalidated": result.stale_summary_count,
            },
        )
        result.finish(final_status)
        await self._workspace.operations.close_run(run_id, "completed")
        return result

    async def _record_blame_artifact(
        self,
        repo_path: Path,
        chain: BlameChain,
        repo_id: str,
        run_id: str,
        snapshot_id: str,
    ) -> str:
        payload = {
            "blame_id": chain.blame_id,
            "repo_id": chain.repo_id,
            "snapshot_id": chain.snapshot_id,
            "file_path": chain.file_path,
            "git_sha": chain.git_sha,
            "worktree_snapshot_id": chain.worktree_snapshot_id,
            "line_entries": [
                {
                    "line_no": line.line_no,
                    "commit_sha": line.commit_sha,
                    "author_time": line.author_time,
                    "summary": line.summary,
                    "original_file_path": line.original_file_path,
                    "original_line_no": line.original_line_no,
                }
                for line in chain.line_entries
            ],
            "diagnostics": [diagnostic.to_dict() for diagnostic in chain.diagnostics],
        }
        data = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
        digest = hashlib.sha256(data).hexdigest()
        artifact_id = f"art:blame:{digest[:16]}"
        safe_file = chain.file_path.replace("/", "__")
        out_dir = repo_path / ".llm-sca" / "blame" / snapshot_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{safe_file}.json"
        out_path.write_bytes(data)
        await self._workspace.artifacts.record_artifact(
            artifact_id,
            "blame",
            out_path.as_uri(),
            "not_required",
            repo_id=repo_id,
            run_id=run_id,
            sha256=digest,
            size_bytes=len(data),
            media_type="application/json",
            metadata={"file_path": chain.file_path, "snapshot_id": snapshot_id},
        )
        return artifact_id


def _make_repo_ref(repo_id: str, repo_path: Path) -> RepoRef:
    return RepoRef(repo_id=repo_id, name=repo_path.name)
