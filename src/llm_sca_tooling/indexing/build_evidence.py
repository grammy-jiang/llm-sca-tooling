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

BUILD_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "tox.ini",
    "noxfile.py",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "tsconfig.build.json",
    "CMakeLists.txt",
    "Makefile",
    "meson.build",
    "compile_commands.json",
    "WORKSPACE",
    "BUILD",
}
TEST_FILES = {"pytest.ini", "conftest.py", "jest.config.js", "jest.config.ts", "vitest.config.ts", ".mocharc.json", "CTestTestfile.cmake"}


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
            if file.is_test or name in TEST_FILES or "test" in file.path.lower():
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
            if name == "package.json":
                try:
                    import json

                    package = json.loads(file.abs_path.read_text(encoding="utf-8"))
                except Exception:
                    package = {}
                for script_name, command in package.get("scripts", {}).items():
                    if script_name in {"test", "build", "lint"}:
                        node = GraphNode(
                            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.BUILD_TARGET, f"npm-script:{script_name}:{file.path}"),
                            node_type=GraphNodeType.BUILD_TARGET,
                            label=f"npm run {script_name}",
                            qualified_name=f"npm-script:{script_name}",
                            repo=repo,
                            snapshot=snapshot,
                            file_path=file.path,
                            provenance=provenance,
                            properties={"kind": "npm_script", "script": script_name, "command": command, "tests_run": False},
                            created_ts=_now_ts(),
                        )
                        result.nodes.append(node)
            if name == "CMakeLists.txt":
                text = file.abs_path.read_text(encoding="utf-8")
                for target_kind in ("add_executable", "add_library"):
                    if target_kind in text:
                        node = GraphNode(
                            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.BUILD_TARGET, f"cmake:{target_kind}:{file.path}"),
                            node_type=GraphNodeType.BUILD_TARGET,
                            label=target_kind,
                            qualified_name=f"cmake:{target_kind}",
                            repo=repo,
                            snapshot=snapshot,
                            file_path=file.path,
                            provenance=provenance,
                            properties={"kind": "cmake_target", "target_kind": target_kind, "tests_run": False},
                            created_ts=_now_ts(),
                        )
                        result.nodes.append(node)
                if "enable_testing" in text or "add_test" in text:
                    node = GraphNode(
                        node_id=node_id(repo.repo_id, snapshot, GraphNodeType.CI_JOB, f"ctest:{file.path}"),
                        node_type=GraphNodeType.CI_JOB,
                        label="ctest",
                        qualified_name="ctest",
                        repo=repo,
                        snapshot=snapshot,
                        file_path=file.path,
                        provenance=provenance,
                        properties={"kind": "ctest", "tests_run": False},
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
