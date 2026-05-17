"""Tests for the file scanner and ignore policy."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.ignore import IgnorePolicy
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.schemas.graph import GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    IndexStatus,
    RepoRef,
    SnapshotRef,
)

NOW = "2026-05-09T12:00:00Z"


def _make_refs(repo_id: str) -> tuple[RepoRef, SnapshotRef]:
    repo = RepoRef(repo_id=repo_id, name="test")
    snap = SnapshotRef(
        repo_id=repo_id,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return repo, snap


def test_scanner_finds_python_files(python_basic_repo: Path) -> None:
    config = IndexingConfig()
    scanner = FileScanner(config)
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(python_basic_repo, repo, snap)
    python_files = [n for n in result.nodes if n.node_type == GraphNodeType.module]
    assert len(python_files) > 0


def test_scanner_emits_repo_node(python_basic_repo: Path) -> None:
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(python_basic_repo, repo, snap)
    repo_nodes = [n for n in result.nodes if n.node_type == GraphNodeType.repo]
    assert len(repo_nodes) == 1


def test_scanner_emits_containment_edges(python_basic_repo: Path) -> None:
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(python_basic_repo, repo, snap)
    from llm_sca_tooling.schemas.graph import GraphEdgeType

    contains_edges = [e for e in result.edges if e.edge_type == GraphEdgeType.contains]
    assert len(contains_edges) > 0


def test_scanner_skips_pycache(tmp_path: Path) -> None:
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-312.pyc").write_bytes(b"\x00" * 100)
    (tmp_path / "main.py").write_text("x = 1")
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(tmp_path, repo, snap)
    assert result.files_scanned >= 1
    # pycache dir should be skipped silently or via diagnostic
    node_paths = [n.file_path for n in result.nodes if n.file_path]
    assert not any("__pycache__" in (p or "") for p in node_paths)


def test_scanner_skips_large_files(tmp_path: Path) -> None:
    big = tmp_path / "huge.py"
    big.write_bytes(b"x = 1\n" * 200_000)  # > 1 MiB
    scanner = FileScanner(IndexingConfig(max_file_size_bytes=1_000))
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(tmp_path, repo, snap)
    assert result.files_skipped >= 1
    skip_diags = [
        d
        for d in result.diagnostics
        if "large" in d.message.lower() or "too large" in d.message.lower()
    ]
    assert skip_diags


def test_scanner_skips_binary_hidden_and_symlink(tmp_path: Path) -> None:
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / ".hidden.py").write_text("x = 1")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("x = 1")
    (tmp_path / "outside_link.py").symlink_to(outside)
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(tmp_path, repo, snap)
    assert result.files_skipped == 2
    assert any(d.code == "SCAN_SKIP_SYMLINK" for d in result.diagnostics)


def test_scanner_marks_generated_and_lock_files(tmp_path: Path) -> None:
    (tmp_path / "schema_pb2.py").write_text("x = 1")
    (tmp_path / "uv.lock").write_text("# lock")
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(tmp_path, repo, snap)
    props = {node.file_path: node.properties for node in result.nodes if node.file_path}
    assert props["schema_pb2.py"]["is_generated"] is True
    assert props["uv.lock"]["is_lock_file"] is True


def test_scanner_hash_failure_uses_empty_hash(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "main.py"
    target.write_text("x = 1")

    def fail_hash(path: Path) -> str:
        raise OSError("unreadable")

    monkeypatch.setattr("llm_sca_tooling.indexing.scanner.hash_file", fail_hash)
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(tmp_path, repo, snap)
    module = next(node for node in result.nodes if node.file_path == "main.py")
    assert module.properties["sha256"] == ""


def test_ignore_policy_skips_git_dir() -> None:
    policy = IgnorePolicy(IndexingConfig())
    assert policy.should_skip_dir(".git") is True
    assert policy.should_skip_dir("src") is False


def test_ignore_policy_governance_allowlist_indexes_dot_dirs(tmp_path: Path) -> None:
    """Regression for May-17 audit Finding 3.

    Hidden directories that hold governance contracts (``.agent``,
    ``.agents``, ``.codex``, ``.github``) must be indexable so the
    implementation-check evidence pipeline can cite them.  Before the
    fix every dot-prefixed dir was skipped unless ``include_hidden`` was
    flipped globally, which would also expose secret-bearing paths like
    ``.env``.
    """
    policy = IgnorePolicy(IndexingConfig())
    assert policy.should_skip_dir(".agent") is False
    assert policy.should_skip_dir(".agents") is False
    assert policy.should_skip_dir(".codex") is False
    assert policy.should_skip_dir(".github") is False


def test_ignore_policy_blocks_secret_dirs_and_files(tmp_path: Path) -> None:
    """Companion to Finding 3 governance allowlist.

    Secret-bearing paths must remain excluded even when the rest of the
    hidden-path policy relaxes.  ``credentials/``, ``secrets/``,
    ``.env`` files, and ``*.key`` / ``*.pem`` files are blocked
    unconditionally.
    """
    policy = IgnorePolicy(IndexingConfig())
    assert policy.should_skip_dir("credentials") is True
    assert policy.should_skip_dir("secrets") is True

    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=1")
    skip, reason = policy.should_skip_file(env_file, env_file.stat().st_size)
    assert skip is True
    assert reason and "secret" in reason.lower()

    env_prod = tmp_path / ".env.production"
    env_prod.write_text("X=2")
    skip, reason = policy.should_skip_file(env_prod, env_prod.stat().st_size)
    assert skip is True

    key_file = tmp_path / "deploy.key"
    key_file.write_text("...")
    skip, reason = policy.should_skip_file(key_file, key_file.stat().st_size)
    assert skip is True

    pem_file = tmp_path / "cert.pem"
    pem_file.write_text("...")
    skip, reason = policy.should_skip_file(pem_file, pem_file.stat().st_size)
    assert skip is True


def test_ignore_policy_detects_python_language(tmp_path: Path) -> None:
    policy = IgnorePolicy(IndexingConfig())
    assert policy.detect_language(tmp_path / "main.py") == "python"
    assert policy.detect_language(tmp_path / "README.md") == "markdown"
    assert policy.detect_language(tmp_path / "unknown.xyz") is None


def test_scanner_produces_repo_relative_paths(python_basic_repo: Path) -> None:
    scanner = FileScanner(IndexingConfig())
    repo, snap = _make_refs("repo:test")
    result = scanner.scan(python_basic_repo, repo, snap)
    for node in result.nodes:
        if node.file_path:
            assert not node.file_path.startswith(
                "/"
            ), f"Absolute path: {node.file_path}"
