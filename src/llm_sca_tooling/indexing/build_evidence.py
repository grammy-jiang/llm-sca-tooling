"""Build and test evidence detector."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendResult
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile, edge_id, node_id
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts

BUILD_FILES = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt", "Pipfile", "poetry.lock", "uv.lock", "tox.ini", "noxfile.py"}
TEST_FILES = {"pytest.ini", "conftest.py"}


class BuildTestEvidenceDetector:
    backend_id = "build-test-evidence"

    def detect(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        now = _now_ts()
        result = BackendResult(backend_id=self.backend_id, backend_version="0.1.0", started_ts=now, ended_ts=now)
        provenance = make_provenance(
            source_tool="evidence-sca.build-evidence",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            derivation=DerivationType.BUILD,
            evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
        )
        for file in files:
            name = Path(file.path).name
            if name in BUILD_FILES:
                node = GraphNode(
                    node_id=node_id(repo.repo_id, snapshot, GraphNodeType.BUILD_TARGET, file.path),
                    node_type=GraphNodeType.BUILD_TARGET,
                    label=file.path,
                    qualified_name=file.path,
                    repo=repo,
                    snapshot=snapshot,
                    file_path=file.path,
                    provenance=provenance,
                    properties={"kind": name, "tests_run": False},
                    created_ts=_now_ts(),
                )
                result.nodes.append(node)
            if file.is_test or name in TEST_FILES:
                node = GraphNode(
                    node_id=node_id(repo.repo_id, snapshot, GraphNodeType.TEST, f"test-evidence:{file.path}"),
                    node_type=GraphNodeType.TEST,
                    label=file.path,
                    qualified_name=f"test-evidence:{file.path}",
                    repo=repo,
                    snapshot=snapshot,
                    file_path=file.path,
                    provenance=provenance,
                    properties={"kind": "test_file_or_config", "tests_run": False},
                    created_ts=_now_ts(),
                )
                result.nodes.append(node)
        for workflow in sorted((repo_root / ".github" / "workflows").glob("*.y*ml")) if (repo_root / ".github" / "workflows").exists() else []:
            rel = workflow.relative_to(repo_root).as_posix()
            node = GraphNode(
                node_id=node_id(repo.repo_id, snapshot, GraphNodeType.CI_JOB, rel),
                node_type=GraphNodeType.CI_JOB,
                label=rel,
                qualified_name=rel,
                repo=repo,
                snapshot=snapshot,
                file_path=rel,
                provenance=provenance,
                properties={"kind": "github_actions", "tests_run": False},
                created_ts=_now_ts(),
            )
            result.nodes.append(node)
        result.files_processed = [file.path for file in files]
        result.ended_ts = _now_ts()
        return result
