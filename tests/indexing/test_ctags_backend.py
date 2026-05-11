"""Tests for the optional ctags backend."""

from __future__ import annotations

from pathlib import Path

import orjson

from llm_sca_tooling.indexing.backends import ctags as ctags_mod
from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.ctags import CtagsBackend
from llm_sca_tooling.indexing.backends.python_ast import PythonASTBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphNodeType
from llm_sca_tooling.schemas.provenance import IndexStatus, RepoRef, SnapshotRef

NOW = "2026-05-09T12:00:00Z"


def _context(repo_root: Path):
    repo = RepoRef(repo_id="repo:ctags", name="ctags")
    snap = SnapshotRef(
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
        snapshot_ref=snap,
        config=IndexingConfig(backend_timeout_ms=100),
        run_id="run:ctags",
    )


def test_ctags_supported_languages() -> None:
    assert "python" in CtagsBackend().supported_languages()


async def test_ctags_missing_records_diagnostic(monkeypatch, tmp_path: Path) -> None:
    async def fake_exec(*_args, **_kwargs) -> tuple[bytes, bytes, int]:
        raise FileNotFoundError("ctags")

    monkeypatch.setattr(ctags_mod, "_exec", fake_exec)
    backend = CtagsBackend()
    result = await backend.index_files(_context(tmp_path), [])
    assert result.diagnostics[0].code == "CTAGS_NOT_AVAILABLE"
    caps = await backend.detect_capabilities(_context(tmp_path), [])
    assert caps.installed is False


async def test_ctags_parses_json_fixture(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def main():\n    return 1\n")
    calls = 0

    async def fake_exec(*args, **_kwargs) -> tuple[bytes, bytes, int]:
        nonlocal calls
        calls += 1
        if args == ("ctags", "--version"):
            return b"Universal Ctags 6.0\n", b"", 0
        payload = orjson.dumps(
            {
                "name": "main",
                "path": str(source),
                "kind": "function",
                "line": 1,
            }
        )
        return payload + b"\n" + b"{bad json}\n", b"", 0

    monkeypatch.setattr(ctags_mod, "_exec", fake_exec)
    backend = CtagsBackend()
    result = await backend.index_files(_context(tmp_path), [source])
    assert backend.backend_version() == "Universal Ctags 6.0"
    assert any(node.node_type == GraphNodeType.function for node in result.nodes)
    assert result.files_processed == 1
    assert calls >= 2


async def test_ctags_process_batch_timeout(monkeypatch, tmp_path: Path) -> None:
    async def fake_exec(*_args, **_kwargs) -> tuple[bytes, bytes, int]:
        raise TimeoutError

    monkeypatch.setattr(ctags_mod, "_exec", fake_exec)
    backend = CtagsBackend()
    result = await backend.index_files(_context(tmp_path), [])
    await backend._process_batch([tmp_path / "app.py"], _context(tmp_path), result)
    assert any(d.code == "CTAGS_TIMEOUT" for d in result.diagnostics)


async def test_ctags_process_batch_exec_error(monkeypatch, tmp_path: Path) -> None:
    async def fake_exec(*_args, **_kwargs) -> tuple[bytes, bytes, int]:
        raise OSError("boom")

    monkeypatch.setattr(ctags_mod, "_exec", fake_exec)
    backend = CtagsBackend()
    result = await backend.index_files(_context(tmp_path), [])
    await backend._process_batch([tmp_path / "app.py"], _context(tmp_path), result)
    assert any(d.code == "CTAGS_EXEC_ERROR" for d in result.diagnostics)


def test_import_backend_package_exports() -> None:
    assert PythonASTBackend().backend_id == "python_ast"
