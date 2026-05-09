"""Repository file scanner and filesystem graph emitter."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.hashing import hash_file, hash_text
from llm_sca_tooling.indexing.ignore import IgnorePolicy, detect_language, is_generated_path
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class ScannedFile(StrictBaseModel):
    path: str
    abs_path: Path
    language: str
    size_bytes: int
    sha256: str
    is_test: bool
    is_generated: bool
    is_vendor: bool = False
    model_config = StrictBaseModel.model_config | {"arbitrary_types_allowed": True}


class ScanResult(StrictBaseModel):
    files: list[ScannedFile] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    files_skipped: int = 0


def node_id(repo_id: str, snapshot: SnapshotRef, node_type: GraphNodeType, key: str) -> str:
    basis = f"{repo_id}|{_snapshot_key(snapshot)}|{node_type.value}|{key}"
    return f"node:{hash_text(basis, length=32)}"


def edge_id(repo_id: str, snapshot: SnapshotRef, edge_type: GraphEdgeType, source_id: str, target_id: str) -> str:
    basis = f"{repo_id}|{_snapshot_key(snapshot)}|{edge_type.value}|{source_id}|{target_id}"
    return f"edge:{hash_text(basis, length=32)}"


def _snapshot_key(snapshot: SnapshotRef) -> str:
    if snapshot.dirty and snapshot.worktree_snapshot_id:
        return snapshot.worktree_snapshot_id
    return snapshot.git_sha or snapshot.worktree_snapshot_id or snapshot.snapshot_label or "unknown"


class FileScanner:
    def __init__(self, config: IndexingConfig) -> None:
        self.config = config
        self.ignore = IgnorePolicy(config)

    def scan(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, *, run_id: str | None = None) -> ScanResult:
        result = ScanResult()
        provenance = make_provenance(source_tool="evidence-sca.scanner", repo=repo, snapshot=snapshot, source_run_id=run_id)
        repo_node = GraphNode(
            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.REPO, repo.repo_id),
            node_type=GraphNodeType.REPO,
            label=repo.name or repo.repo_id,
            qualified_name=repo.repo_id,
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            properties={"root_path_hash": repo.root_ref},
            created_ts=_now_ts(),
        )
        result.nodes.append(repo_node)
        directory_nodes: dict[str, GraphNode] = {"": repo_node}
        for root, dirs, files in self._walk(repo_root):
            root_path = Path(root)
            dirs[:] = [directory for directory in dirs if not self.ignore.skip_dir(root_path / directory, repo_root)]
            rel_dir = "" if root_path == repo_root else root_path.relative_to(repo_root).as_posix()
            parent_node = self._ensure_directory(rel_dir, repo, snapshot, provenance, directory_nodes, result)
            for filename in files:
                abs_path = root_path / filename
                rel = abs_path.relative_to(repo_root).as_posix()
                reason = self.ignore.skip_file_reason(abs_path, repo_root)
                if reason:
                    result.files_skipped += 1
                    result.diagnostics.append(
                        IndexDiagnostic(
                            diagnostic_id=f"diag:{hash_text(rel + reason)}",
                            severity=Severity.WARNING,
                            code=f"file_skipped_{reason}",
                            message=f"Skipped {rel}: {reason}",
                            file_path=rel,
                        )
                    )
                    continue
                scanned = ScannedFile(
                    path=rel,
                    abs_path=abs_path,
                    language=detect_language(abs_path),
                    size_bytes=abs_path.stat().st_size,
                    sha256=hash_file(abs_path),
                    is_test=is_test_path(rel),
                    is_generated=is_generated_path(rel),
                )
                result.files.append(scanned)
                file_node_type = GraphNodeType.DOCUMENT if scanned.language == "markdown" else GraphNodeType.FILE
                file_node = GraphNode(
                    node_id=node_id(repo.repo_id, snapshot, file_node_type, rel),
                    node_type=file_node_type,
                    label=rel,
                    qualified_name=rel,
                    repo=repo,
                    snapshot=snapshot,
                    file_path=rel,
                    provenance=provenance,
                    properties={
                        "language": scanned.language,
                        "sha256": scanned.sha256,
                        "size_bytes": scanned.size_bytes,
                        "is_test": scanned.is_test,
                        "is_generated": scanned.is_generated,
                    },
                    created_ts=_now_ts(),
                )
                result.nodes.append(file_node)
                result.edges.append(self._contains(repo, snapshot, provenance, parent_node.node_id, file_node.node_id))
                if scanned.language == "python":
                    module_name = module_name_for_path(rel)
                    module_node = GraphNode(
                        node_id=node_id(repo.repo_id, snapshot, GraphNodeType.MODULE, rel),
                        node_type=GraphNodeType.MODULE,
                        label=module_name,
                        qualified_name=module_name,
                        repo=repo,
                        snapshot=snapshot,
                        file_path=rel,
                        provenance=provenance,
                        properties={"language": "python", "is_test": scanned.is_test},
                        created_ts=_now_ts(),
                    )
                    result.nodes.append(module_node)
                    result.edges.append(self._contains(repo, snapshot, provenance, file_node.node_id, module_node.node_id))
                    if filename == "__init__.py":
                        package_node = GraphNode(
                            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.PACKAGE, rel_dir or module_name),
                            node_type=GraphNodeType.PACKAGE,
                            label=module_name,
                            qualified_name=module_name,
                            repo=repo,
                            snapshot=snapshot,
                            file_path=rel,
                            provenance=provenance,
                            properties={"language": "python"},
                            created_ts=_now_ts(),
                        )
                        result.nodes.append(package_node)
                        result.edges.append(self._contains(repo, snapshot, provenance, parent_node.node_id, package_node.node_id))
        return result

    def _walk(self, repo_root: Path):
        return os.walk(repo_root, followlinks=self.config.follow_symlinks)

    def _ensure_directory(
        self,
        rel_dir: str,
        repo: RepoRef,
        snapshot: SnapshotRef,
        provenance,
        directory_nodes: dict[str, GraphNode],
        result: ScanResult,
    ) -> GraphNode:
        if rel_dir in directory_nodes:
            return directory_nodes[rel_dir]
        parent = str(Path(rel_dir).parent).replace(".", "")
        parent_node = self._ensure_directory(parent, repo, snapshot, provenance, directory_nodes, result)
        directory_node = GraphNode(
            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.DIRECTORY, rel_dir),
            node_type=GraphNodeType.DIRECTORY,
            label=rel_dir,
            qualified_name=rel_dir,
            repo=repo,
            snapshot=snapshot,
            file_path=None,
            provenance=provenance,
            properties={},
            created_ts=_now_ts(),
        )
        directory_nodes[rel_dir] = directory_node
        result.nodes.append(directory_node)
        result.edges.append(self._contains(repo, snapshot, provenance, parent_node.node_id, directory_node.node_id))
        return directory_node

    def _contains(self, repo: RepoRef, snapshot: SnapshotRef, provenance, source_id: str, target_id: str) -> GraphEdge:
        return GraphEdge(
            edge_id=edge_id(repo.repo_id, snapshot, GraphEdgeType.CONTAINS, source_id, target_id),
            edge_type=GraphEdgeType.CONTAINS,
            source_id=source_id,
            target_id=target_id,
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            confidence=1.0,
            properties={},
            created_ts=_now_ts(),
        )


def module_name_for_path(path: str) -> str:
    without_suffix = path[:-3] if path.endswith(".py") else path
    parts = [part for part in without_suffix.split("/") if part not in {"src", "__init__"}]
    return ".".join(parts) or "__init__"


def is_test_path(path: str) -> bool:
    name = Path(path).name
    return path.startswith(("tests/", "test/")) or name.startswith("test_") or name.endswith("_test.py")
