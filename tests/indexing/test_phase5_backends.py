from __future__ import annotations

import json
import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.backends.cpp import CppBackend
from llm_sca_tooling.indexing.backends.cpp.compile_commands import CompileCommands
from llm_sca_tooling.indexing.backends.cross_check import CrossChecker
from llm_sca_tooling.indexing.backends.java.capability import JAVA_BACKEND_ENABLED
from llm_sca_tooling.indexing.backends.java.java_backend import JavaBackend
from llm_sca_tooling.indexing.backends.python import PythonBackend
from llm_sca_tooling.indexing.backends.registry import BackendRegistry
from llm_sca_tooling.indexing.backends.typescript import TypeScriptBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.indexing.service import graph_build
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef
from llm_sca_tooling.storage import initialize_workspace


def test_backend_registry_capabilities_are_stable() -> None:
    registry = BackendRegistry()
    for backend in (PythonBackend(), TypeScriptBackend(), CppBackend(), JavaBackend()):
        registry.register(backend)
    report = registry.capability_report()
    assert [item.backend_id for item in report] == [
        "cpp.backend",
        "java.jdt",
        "python.backend",
        "typescript.backend",
    ]
    assert all(
        item.supported_node_types or item.supported_edge_types for item in report
    )
    assert not JavaBackend().check_availability().available
    assert JAVA_BACKEND_ENABLED is False


def test_typescript_backend_emits_symbols_imports_and_calls(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "ts_repo")
    (repo / "src").mkdir()
    (repo / "src" / "util.ts").write_text(
        "export function util(x: number) { return x + 1; }\n", encoding="utf-8"
    )
    (repo / "src" / "main.ts").write_text(
        "import { util } from './util';\nexport function run() { return util(1); }\n",
        encoding="utf-8",
    )
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "version": "1.0.0",
                "scripts": {"test": "jest", "build": "tsc"},
                "devDependencies": {"jest": "1.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (repo / "tsconfig.json").write_text("{}", encoding="utf-8")
    result = _backend_result(repo, TypeScriptBackend())
    assert any(
        node.node_type == GraphNodeType.FUNCTION and node.label == "run"
        for node in result.nodes
    )
    assert any(edge.edge_type == GraphEdgeType.IMPORTS for edge in result.edges)
    assert any(edge.edge_type == GraphEdgeType.CALLS for edge in result.edges)


def test_cpp_backend_compile_commands_symbols_includes_and_calls(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "cpp_repo")
    (repo / "src").mkdir()
    (repo / "src" / "util.h").write_text("int callee();\n", encoding="utf-8")
    (repo / "src" / "util.cpp").write_text(
        '#include "util.h"\nint callee(){ return 1; }\n', encoding="utf-8"
    )
    (repo / "src" / "main.cpp").write_text(
        '#include "util.h"\nint caller(){ return callee(); }\n', encoding="utf-8"
    )
    (repo / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nadd_executable(app src/main.cpp src/util.cpp)\nenable_testing()\nadd_test(NAME app_test COMMAND app)\n",
        encoding="utf-8",
    )
    (repo / "compile_commands.json").write_text(
        json.dumps(
            [
                {
                    "directory": str(repo),
                    "command": "c++ -std=c++20 -I src -c src/main.cpp",
                    "file": str(repo / "src" / "main.cpp"),
                }
            ]
        ),
        encoding="utf-8",
    )
    commands, diagnostics = CompileCommands().load(repo)
    assert diagnostics == []
    assert commands[0].repo_relative_file == "src/main.cpp"
    result = _backend_result(repo, CppBackend())
    assert any(
        node.node_type == GraphNodeType.FUNCTION and node.label == "caller"
        for node in result.nodes
    )
    assert any(edge.edge_type == GraphEdgeType.IMPORTS for edge in result.edges)
    assert any(edge.edge_type == GraphEdgeType.CALLS for edge in result.edges)


def test_graph_build_indexes_typescript_and_cpp(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "mixed")
    (repo / "src").mkdir()
    (repo / "src" / "main.ts").write_text(
        "function helper(){ return 1; }\nfunction run(){ return helper(); }\n",
        encoding="utf-8",
    )
    (repo / "src" / "main.cpp").write_text(
        "int helper(){ return 1; }\nint run(){ return helper(); }\n", encoding="utf-8"
    )
    (repo / "package.json").write_text(
        '{"scripts":{"test":"vitest"}}', encoding="utf-8"
    )
    (repo / "CMakeLists.txt").write_text(
        "add_executable(app src/main.cpp)\nenable_testing()\n", encoding="utf-8"
    )
    workspace = tmp_path / "workspace"
    result = graph_build(repo, workspace_path=workspace)
    store = initialize_workspace(workspace)
    try:
        functions = store.graph.fetch_nodes_by_type(
            result.repo_id, GraphNodeType.FUNCTION, snapshot_id=result.snapshot_id
        )
        build_targets = store.graph.fetch_nodes_by_type(
            result.repo_id, GraphNodeType.BUILD_TARGET, snapshot_id=result.snapshot_id
        )
        assert any(
            node.properties.get("language") == "typescript" for node in functions
        )
        assert any(node.properties.get("language") == "cpp" for node in functions)
        assert build_targets
    finally:
        store.close()


def test_cross_checker_agreement_states(python_basic_repo) -> None:
    result = _backend_result(python_basic_repo, PythonBackend())
    edge = next(edge for edge in result.edges if edge.edge_type == GraphEdgeType.CALLS)
    agreement, diagnostics = CrossChecker().compare(
        [edge, edge.model_copy(deep=True)], ["python.ast", "python.pyan3"]
    )
    assert agreement.agreement == "confirmed"
    conflict = edge.model_copy(deep=True)
    conflict.target_id = "node:other"
    agreement, diagnostics = CrossChecker().compare([edge, conflict], ["a", "b"])
    assert agreement.agreement == "conflicting"
    assert diagnostics


def test_missing_compile_commands_is_diagnostic(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "cpp_degraded")
    (repo / "src").mkdir()
    (repo / "src" / "main.cpp").write_text(
        "int main(){ return 0; }\n", encoding="utf-8"
    )
    result = _backend_result(repo, CppBackend())
    assert any(
        diagnostic.code == "COMPILE_COMMANDS_MISSING"
        for diagnostic in result.diagnostics
    )


def _backend_result(repo_root: Path, backend):
    config = IndexingConfig()
    repo_ref = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo_ref.repo_id, repo_root, config)
    files = FileScanner(config).scan(repo_root, repo_ref, snapshot).files
    return backend.index_files(repo_root, repo_ref, snapshot, files)


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    return root
