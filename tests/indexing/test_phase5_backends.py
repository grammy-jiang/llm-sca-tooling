"""Phase 5 backend expansion tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendResult, IndexingContext
from llm_sca_tooling.indexing.backends.capability import BackendOutput, BackendRunStats
from llm_sca_tooling.indexing.backends.cpp import CppBackend
from llm_sca_tooling.indexing.backends.cpp.compile_commands import (
    parse_compile_commands,
)
from llm_sca_tooling.indexing.backends.cpp.ctest_detection import detect_ctest_commands
from llm_sca_tooling.indexing.backends.cross_check import CrossChecker
from llm_sca_tooling.indexing.backends.fact_reconciler import FactReconciler
from llm_sca_tooling.indexing.backends.java import JavaBackend
from llm_sca_tooling.indexing.backends.python.pyan3_adapter import Pyan3Adapter
from llm_sca_tooling.indexing.backends.python.pyright_adapter import PyrightAdapter
from llm_sca_tooling.indexing.backends.python.python_backend import PythonBackend
from llm_sca_tooling.indexing.backends.registry import BackendRegistry
from llm_sca_tooling.indexing.backends.typescript import TypeScriptBackend
from llm_sca_tooling.indexing.backends.typescript.package_meta import (
    read_package_metadata,
)
from llm_sca_tooling.indexing.backends.typescript.ts_test_detection import (
    detect_test_runners,
)
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import IndexStatus, RepoRef, SnapshotRef
from llm_sca_tooling.storage import WorkspaceStore

NOW = "2026-05-09T12:00:00Z"
FIXTURES = Path(__file__).parent / "backends" / "fixtures"


def _context(repo_root: Path) -> IndexingContext:
    repo = RepoRef(repo_id="repo:phase5", name=repo_root.name)
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return IndexingContext(
        repo_root=repo_root,
        repo_ref=repo,
        snapshot_ref=snapshot,
        config=IndexingConfig(),
        run_id="run:phase5",
    )


def _labels(result: BackendResult, node_type: GraphNodeType) -> set[str]:
    return {node.label for node in result.nodes if node.node_type == node_type}


async def test_backend_registry_reports_capabilities() -> None:
    registry = BackendRegistry()
    registry.register(TypeScriptBackend())
    registry.register(CppBackend())
    registry.register(JavaBackend())

    assert [backend.backend_id for backend in registry.list_backends()] == [
        "typescript.tsmorph",
        "cpp.libclang",
        "java.jdt",
    ]
    assert [backend.backend_id for backend in registry.available_backends("cpp")] == [
        "cpp.libclang"
    ]
    report = registry.capability_report()
    assert {item.backend_id for item in report} == {
        "typescript.tsmorph",
        "cpp.libclang",
        "java.jdt",
    }
    availability = await registry.availability_check()
    assert {item.backend_id for item in availability} == {
        "typescript.tsmorph",
        "cpp.libclang",
        "java.jdt",
    }


def test_backend_registry_rejects_duplicate_backend() -> None:
    registry = BackendRegistry()
    registry.register(TypeScriptBackend())
    try:
        registry.register(TypeScriptBackend())
    except ValueError as exc:
        assert "duplicate backend" in str(exc)
    else:
        raise AssertionError("duplicate backend was accepted")


async def test_typescript_backend_emits_symbols_imports_calls_and_build_evidence() -> (
    None
):
    repo = FIXTURES / "typescript_repo"
    context = _context(repo)
    files = sorted(repo.rglob("*.*"))

    result = await TypeScriptBackend().index_files(context, files)

    assert {"App"} <= _labels(result, GraphNodeType.class_)
    assert {"main", "helper", "plain"} <= _labels(result, GraphNodeType.function)
    assert {"Greeter"} <= _labels(result, GraphNodeType.interface)
    assert any(edge.edge_type == GraphEdgeType.imports for edge in result.edges)
    assert any(edge.edge_type == GraphEdgeType.calls for edge in result.edges)
    assert {"build", "lint", "test"} <= _labels(result, GraphNodeType.build_target)
    assert "jest" in _labels(result, GraphNodeType.ci_job)
    assert all(
        "typescript.tsmorph" in node.provenance.source_tool for node in result.nodes
    )


def test_typescript_package_metadata_and_invalid_json(tmp_path: Path) -> None:
    package = read_package_metadata(FIXTURES / "typescript_repo")
    assert package.name == "phase5-ts-fixture"
    assert package.version == "1.0.0"
    assert package.dependencies["left-pad"] == "1.3.0"
    assert detect_test_runners(FIXTURES / "typescript_repo", package) == ["jest"]

    (tmp_path / "package.json").write_text("{not-json")
    invalid = read_package_metadata(tmp_path)
    assert invalid.diagnostics[0].code == "FILE_PARSE_ERROR"


async def test_cpp_backend_emits_symbols_includes_calls_and_ctest() -> None:
    repo = FIXTURES / "cpp_repo"
    context = _context(repo)
    files = sorted(repo.rglob("*.*"))

    result = await CppBackend().index_files(context, files)

    assert {"Widget"} <= _labels(result, GraphNodeType.class_)
    assert {"helper", "run", "main"} <= _labels(result, GraphNodeType.function)
    assert any(edge.edge_type == GraphEdgeType.imports for edge in result.edges)
    assert any(edge.edge_type == GraphEdgeType.calls for edge in result.edges)
    assert "ctest" in _labels(result, GraphNodeType.ci_job)
    assert "cmake-target:fixture" in _labels(result, GraphNodeType.build_target)


def test_cpp_compile_commands_parser_and_degradation(tmp_path: Path) -> None:
    parsed = parse_compile_commands(FIXTURES / "cpp_repo")
    assert parsed.records[0].file == "src/lib.cpp"
    assert parsed.records[0].include_dirs == ["include"]
    assert parsed.records[0].defines == ["DEBUG"]
    assert parsed.records[0].standard == "-std=c++20"
    assert "ctest" in detect_ctest_commands(FIXTURES / "cpp_repo")

    missing = parse_compile_commands(tmp_path)
    assert missing.diagnostics[0].code == "COMPILE_COMMANDS_MISSING"

    (tmp_path / "compile_commands.json").write_text('{"not": "a-list"}')
    invalid = parse_compile_commands(tmp_path)
    assert invalid.diagnostics[0].code == "FILE_PARSE_ERROR"

    source = tmp_path / "src" / "main.cpp"
    source.parent.mkdir()
    source.write_text("int main() { return 0; }\n")
    (tmp_path / "compile_commands.json").write_text(
        f'[{{"directory": "{tmp_path}", "file": "{source}", '
        '"command": "c++ -Iinc -DTEST -std=c++17 -c src/main.cpp"}]'
    )
    command_record = parse_compile_commands(tmp_path).records[0]
    assert command_record.file == "src/main.cpp"
    assert command_record.command is not None


async def test_python_phase5_adapters_degrade_without_crashing(
    python_basic_repo: Path,
) -> None:
    context = _context(python_basic_repo)
    files = sorted(python_basic_repo.rglob("*.py"))

    pyan = Pyan3Adapter()
    pyan_availability = await pyan.check_availability(context)
    pyan_capabilities = await pyan.detect_capabilities(context, files)
    pyan_result = await pyan.index_files(context, files)
    assert pyan_availability.available
    assert pyan_capabilities.backend_id == "python.pyan3"
    assert pyan_result.backend_id == "python.pyan3"
    assert all(edge.edge_type == GraphEdgeType.calls for edge in pyan_result.edges)

    pyright_availability = await PyrightAdapter().check_availability(context)
    assert pyright_availability.backend_id == "python.pyright"
    assert isinstance(pyright_availability.available, bool)

    unified = await PythonBackend().index_files(context, files)
    assert PythonBackend().backend_id == "python"
    assert unified.nodes
    assert any(
        diagnostic.backend_id == "python.pyright" for diagnostic in unified.diagnostics
    )


async def test_java_backend_disabled_and_enabled_paths(
    monkeypatch, tmp_path: Path
) -> None:
    repo = tmp_path / "java_repo"
    shutil.copytree(FIXTURES / "java_repo", repo)
    context = _context(repo)
    java_file = repo / "src" / "App.java"
    backend = JavaBackend()

    monkeypatch.delenv("LLM_SCA_JAVA_BACKEND_ENABLED", raising=False)
    disabled = await backend.check_availability(context)
    disabled_capabilities = await backend.detect_capabilities(context, [java_file])
    disabled_result = await backend.index_files(context, [java_file])
    assert not disabled.available
    assert not disabled_capabilities.installed
    assert disabled_result.nodes == []

    monkeypatch.setenv("LLM_SCA_JAVA_BACKEND_ENABLED", "1")
    enabled = await backend.check_availability(context)
    enabled_capabilities = await backend.detect_capabilities(context, [java_file])
    enabled_result = await backend.index_files(context, [java_file])
    assert enabled.backend_id == "java.jdt"
    assert enabled_capabilities.supported_languages == ["java"]
    assert {"App"} <= _labels(enabled_result, GraphNodeType.class_)
    assert {"helper", "run"} <= _labels(enabled_result, GraphNodeType.method)
    assert any(edge.edge_type == GraphEdgeType.imports for edge in enabled_result.edges)
    assert any(edge.edge_type == GraphEdgeType.calls for edge in enabled_result.edges)


def test_fact_reconciler_candidate_confirmed_conflicting() -> None:
    context = _context(FIXTURES / "typescript_repo")
    source = _node(context, "source", GraphNodeType.function)
    target_a = _node(context, "target_a", GraphNodeType.function)
    target_b = _node(context, "target_b", GraphNodeType.function)
    same_node_a = _node(context, "same_a", GraphNodeType.function, "same")
    same_node_b = _node(context, "same_b", GraphNodeType.function, "same")

    first = BackendResult("first", "1")
    first.nodes = [same_node_a]
    first.edges = [
        _edge(
            context, "first-call", GraphEdgeType.calls, source.node_id, target_a.node_id
        )
    ]
    second = BackendResult("second", "1")
    second.nodes = [same_node_b]
    second.edges = [
        _edge(
            context,
            "second-conflict",
            GraphEdgeType.calls,
            source.node_id,
            target_b.node_id,
        ),
        _edge(
            context,
            "second-candidate",
            GraphEdgeType.calls,
            target_a.node_id,
            target_b.node_id,
        ),
    ]

    reconciled = FactReconciler().reconcile([second, first])
    cross_checked = CrossChecker().reconcile([first, second])

    agreements = {(item.fact_type, item.agreement) for item in reconciled.agreements}
    assert ("node", "confirmed") in agreements
    assert ("edge", "candidate") in agreements
    assert ("edge", "conflicting") in agreements
    assert any(
        diagnostic.code == "CROSS_CHECK_CONFLICT"
        for diagnostic in reconciled.diagnostics
    )
    assert cross_checked.diagnostics[0].code == "CROSS_CHECK_CONFLICT"
    assert (
        FactReconciler().reconcile([second, first]).agreements == reconciled.agreements
    )


def test_backend_output_hash_and_conversion() -> None:
    context = _context(FIXTURES / "typescript_repo")
    node = _node(context, "hash-node", GraphNodeType.function)
    output = BackendOutput(
        backend_id="hash.backend",
        backend_version="1",
        repo_id=context.repo_ref.repo_id,
        snapshot_id=context.snapshot_ref.git_sha or "snapshot",
        git_sha=context.snapshot_ref.git_sha,
        worktree_snapshot_id=None,
        nodes=[node],
        run_stats=BackendRunStats(files_scanned=1),
    )
    converted = output.to_backend_result()
    assert output.output_hash == output.output_hash
    assert converted.backend_id == "hash.backend"
    assert converted.files_processed == 1


async def test_graph_build_integrates_typescript_and_cpp_backends(
    workspace: WorkspaceStore, tmp_path: Path
) -> None:
    ts_repo = tmp_path / "ts_repo"
    cpp_repo = tmp_path / "cpp_repo"
    shutil.copytree(FIXTURES / "typescript_repo", ts_repo)
    shutil.copytree(FIXTURES / "cpp_repo", cpp_repo)
    indexer = IndexingService(workspace)

    ts_result = await indexer.graph_build(ts_repo)
    cpp_result = await indexer.graph_build(cpp_repo)

    assert ts_result.backend_versions["typescript"] == "phase5-python-fallback"
    assert cpp_result.backend_versions["cpp"] == "phase5-python-fallback"
    ts_functions = await workspace.queries.fetch_nodes_by_type(
        ts_result.repo_id, GraphNodeType.function
    )
    cpp_functions = await workspace.queries.fetch_nodes_by_type(
        cpp_result.repo_id, GraphNodeType.function
    )
    assert any(node.label == "main" for node in ts_functions)
    assert any(node.label == "helper" for node in cpp_functions)


def _node(
    context: IndexingContext,
    suffix: str,
    node_type: GraphNodeType,
    label: str | None = None,
) -> GraphNode:
    label = label or suffix
    return GraphNode(
        node_id=make_node_id(context.repo_ref.repo_id, node_type.value, suffix),
        node_type=node_type,
        label=label,
        qualified_name=label,
        repo=context.repo_ref,
        snapshot=context.snapshot_ref,
        file_path="fixture.py",
        provenance=parser_provenance(context.repo_ref, context.snapshot_ref, "test"),
        created_ts=NOW,
    )


def _edge(
    context: IndexingContext,
    suffix: str,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
) -> GraphEdge:
    return GraphEdge(
        edge_id=make_edge_id(
            context.repo_ref.repo_id,
            edge_type.value,
            f"{source_id}:{suffix}",
            target_id,
        ),
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=context.repo_ref,
        snapshot=context.snapshot_ref,
        provenance=parser_provenance(context.repo_ref, context.snapshot_ref, "test"),
        confidence=0.7,
        created_ts=NOW,
    )
