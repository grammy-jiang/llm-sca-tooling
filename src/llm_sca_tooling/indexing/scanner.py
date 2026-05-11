"""File tree scanner — discovers files and emits graph nodes/edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import hash_file, make_edge_id, make_node_id
from llm_sca_tooling.indexing.ignore import IgnorePolicy
from llm_sca_tooling.indexing.provenance import scanner_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

__all__ = ["ScanResult", "FileScanner"]


@dataclass
class ScanResult:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


class FileScanner:
    """Walk a repository tree and emit file/directory graph nodes."""

    def __init__(self, config: IndexingConfig) -> None:
        self._config = config
        self._ignore = IgnorePolicy(config)

    def scan(
        self,
        repo_root: Path,
        repo_ref: RepoRef,
        snapshot_ref: SnapshotRef,
    ) -> ScanResult:
        """Scan *repo_root* and return typed graph facts."""
        result = ScanResult()
        prov = scanner_provenance(repo_ref, snapshot_ref)
        now = _now()

        # Emit repo node
        repo_node_id = make_node_id(repo_ref.repo_id, "repo", repo_ref.repo_id)
        result.nodes.append(
            GraphNode(
                node_id=repo_node_id,
                node_type=GraphNodeType.repo,
                label=repo_root.name,
                qualified_name=repo_ref.repo_id,
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=prov,
                properties={"root_name": repo_root.name},
                created_ts=now,
            )
        )

        self._walk(
            repo_root, repo_root, repo_node_id, repo_ref, snapshot_ref, result, now
        )
        return result

    def _walk(
        self,
        root: Path,
        current: Path,
        parent_node_id: str,
        repo_ref: RepoRef,
        snapshot_ref: SnapshotRef,
        result: ScanResult,
        now: str,
    ) -> None:
        try:
            entries = sorted(current.iterdir())
        except PermissionError as exc:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="SCAN_PERMISSION",
                    message=f"Cannot read directory {current.relative_to(root)}: {exc}",
                )
            )
            return

        prov = scanner_provenance(repo_ref, snapshot_ref)

        for entry in entries:
            rel_path = str(entry.relative_to(root))

            if entry.is_symlink() and not self._config.follow_symlinks:
                result.diagnostics.append(
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.info,
                        code="SCAN_SKIP_SYMLINK",
                        message=f"Skipped symlink: {rel_path}",
                        file_path=rel_path,
                    )
                )
                continue

            if entry.is_dir():
                if self._ignore.should_skip_dir(entry.name):
                    result.diagnostics.append(
                        IndexingDiagnostic(
                            severity=DiagnosticSeverity.info,
                            code="SCAN_SKIP_DIR",
                            message=f"Skipped directory: {rel_path}",
                            file_path=rel_path,
                        )
                    )
                    continue

                is_pkg = (entry / "__init__.py").exists()
                node_type = GraphNodeType.package if is_pkg else GraphNodeType.directory
                dir_id = make_node_id(repo_ref.repo_id, node_type.value, rel_path)
                result.nodes.append(
                    GraphNode(
                        node_id=dir_id,
                        node_type=node_type,
                        label=entry.name,
                        qualified_name=rel_path.replace("/", "."),
                        file_path=rel_path,
                        repo=repo_ref,
                        snapshot=snapshot_ref,
                        provenance=prov,
                        properties={"is_package": is_pkg},
                        created_ts=now,
                    )
                )
                result.edges.append(
                    GraphEdge(
                        edge_id=make_edge_id(
                            repo_ref.repo_id, "contains", parent_node_id, dir_id
                        ),
                        edge_type=GraphEdgeType.contains,
                        source_id=parent_node_id,
                        target_id=dir_id,
                        repo=repo_ref,
                        snapshot=snapshot_ref,
                        provenance=prov,
                        created_ts=now,
                    )
                )
                self._walk(root, entry, dir_id, repo_ref, snapshot_ref, result, now)

            elif entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0

                skip, reason = self._ignore.should_skip_file(entry, size)
                if skip:
                    result.files_skipped += 1
                    result.diagnostics.append(
                        IndexingDiagnostic(
                            severity=DiagnosticSeverity.info,
                            code="SCAN_SKIP_FILE",
                            message=f"Skipped {rel_path}: {reason}",
                            file_path=rel_path,
                        )
                    )
                    continue

                lang = self._ignore.detect_language(entry)
                is_test = self._ignore.is_test_file(rel_path)
                is_gen = self._ignore.is_generated_file(entry)
                is_lock = self._ignore.is_lock_file(entry)

                try:
                    file_hash = hash_file(entry)
                except OSError:
                    file_hash = ""

                node_type = (
                    GraphNodeType.module if lang == "python" else GraphNodeType.file
                )
                file_id = make_node_id(repo_ref.repo_id, node_type.value, rel_path)
                result.nodes.append(
                    GraphNode(
                        node_id=file_id,
                        node_type=node_type,
                        label=entry.name,
                        qualified_name=rel_path,
                        file_path=rel_path,
                        repo=repo_ref,
                        snapshot=snapshot_ref,
                        provenance=prov,
                        properties={
                            "language": lang,
                            "size_bytes": size,
                            "sha256": file_hash,
                            "is_test": is_test,
                            "is_generated": is_gen,
                            "is_lock_file": is_lock,
                        },
                        created_ts=now,
                    )
                )
                result.edges.append(
                    GraphEdge(
                        edge_id=make_edge_id(
                            repo_ref.repo_id, "contains", parent_node_id, file_id
                        ),
                        edge_type=GraphEdgeType.contains,
                        source_id=parent_node_id,
                        target_id=file_id,
                        repo=repo_ref,
                        snapshot=snapshot_ref,
                        provenance=prov,
                        created_ts=now,
                    )
                )
                result.files_scanned += 1
