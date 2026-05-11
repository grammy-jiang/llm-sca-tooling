"""Build and test evidence detector.

Detects pytest config, test directories, CI workflows, and package metadata
as graph evidence nodes.  Does NOT run tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from llm_sca_tooling.indexing.hashing import make_node_id
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    Provenance,
    RepoRef,
    SnapshotRef,
)

__all__ = ["BuildEvidenceDetector", "BuildEvidence"]

_PACKAGE_META_FILES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "requirements-dev.txt",
        "Pipfile",
        "poetry.lock",
        "uv.lock",
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
        "tox.ini",
        "noxfile.py",
    }
)
_TEST_CONFIG_FILES = frozenset(
    {
        "pytest.ini",
        "conftest.py",
        "jest.config.js",
        "vitest.config.js",
        ".mocharc.json",
        "CTestTestfile.cmake",
    }
)
_CI_PATTERNS = [
    "**/.github/workflows/*.yml",
    "**/.github/workflows/*.yaml",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
]


@dataclass
class BuildEvidence:
    nodes: list[GraphNode] = field(default_factory=list)
    has_pytest: bool = False
    has_tests_dir: bool = False
    has_ci: bool = False
    package_metadata_files: list[str] = field(default_factory=list)
    ci_files: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class BuildEvidenceDetector:
    """Scan a repository for build and test evidence."""

    def detect(
        self, repo_root: Path, repo_ref: RepoRef, snapshot_ref: SnapshotRef
    ) -> BuildEvidence:
        evidence = BuildEvidence()
        now = _now()

        def make_prov(derivation: DerivationType = DerivationType.build) -> Provenance:
            return make_provenance(
                repo_ref,
                snapshot_ref,
                source_tool="llm-sca-tooling.build_evidence",
                derivation=derivation,
                evidence_strength=EvidenceStrength.structured_repository,
                confidence=1.0,
            )

        # Package metadata
        for f in repo_root.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            name = f.name

            if name in _PACKAGE_META_FILES:
                evidence.package_metadata_files.append(rel)
                node_id = make_node_id(repo_ref.repo_id, "build_target", rel)
                evidence.nodes.append(
                    GraphNode(
                        node_id=node_id,
                        node_type=GraphNodeType.build_target,
                        label=name,
                        qualified_name=rel,
                        file_path=rel,
                        repo=repo_ref,
                        snapshot=snapshot_ref,
                        provenance=make_prov(),
                        properties={"kind": "package_metadata"},
                        created_ts=now,
                    )
                )
                if name in {"pyproject.toml", "pytest.ini", "tox.ini"}:
                    evidence.has_pytest = True

            if name in _TEST_CONFIG_FILES:
                evidence.has_pytest = True

        # CI workflow files
        for pattern in [".github/workflows"]:
            workflows_dir = repo_root / pattern
            if workflows_dir.exists():
                for wf in workflows_dir.glob("*.yml"):
                    rel = str(wf.relative_to(repo_root)).replace("\\", "/")
                    evidence.ci_files.append(rel)
                    evidence.has_ci = True
                    node_id = make_node_id(repo_ref.repo_id, "ci_job", rel)
                    evidence.nodes.append(
                        GraphNode(
                            node_id=node_id,
                            node_type=GraphNodeType.ci_job,
                            label=wf.name,
                            qualified_name=rel,
                            file_path=rel,
                            repo=repo_ref,
                            snapshot=snapshot_ref,
                            provenance=make_prov(),
                            properties={"kind": "github_actions"},
                            created_ts=now,
                        )
                    )

        # Test directories
        for test_dir_name in ["tests", "test"]:
            test_dir = repo_root / test_dir_name
            if test_dir.is_dir():
                evidence.has_tests_dir = True
                evidence.has_pytest = True
                break

        return evidence
