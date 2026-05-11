"""Tests for git blame-chain collection."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing import blame as blame_mod
from llm_sca_tooling.indexing.blame import BlameCollector


class _FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


async def test_collect_missing_file_reports_diagnostic(tmp_path: Path) -> None:
    chain = await BlameCollector().collect(
        tmp_path, "missing.py", "repo:1", "snap:1", git_sha="abc"
    )
    assert chain.line_entries == []
    assert chain.diagnostics[0].code == "BLAME_FILE_NOT_FOUND"


async def test_collect_parses_porcelain(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")
    porcelain = (
        b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 1 1 1\n"
        b"author-time 1710000000\n"
        b"summary initial commit\n"
        b"filename app.py\n"
        b"\tx = 1\n"
    )

    async def fake_exec(*_args, **_kwargs) -> _FakeProcess:
        return _FakeProcess(porcelain)

    monkeypatch.setattr(blame_mod.asyncio, "create_subprocess_exec", fake_exec)
    chain = await BlameCollector().collect(
        tmp_path, "app.py", "repo:1", "snap:1", git_sha="abc"
    )
    assert chain.line_entries[0].commit_sha.startswith("a")
    assert chain.line_entries[0].summary == "initial commit"


async def test_collect_nonzero_git_exit(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")

    async def fake_exec(*_args, **_kwargs) -> _FakeProcess:
        return _FakeProcess(b"", b"fatal: no HEAD", 128)

    monkeypatch.setattr(blame_mod.asyncio, "create_subprocess_exec", fake_exec)
    chain = await BlameCollector().collect(tmp_path, "app.py", "repo:1", "snap:1")
    assert chain.diagnostics[0].code == "BLAME_GIT_ERROR"


async def test_collect_exec_error(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")

    async def fake_exec(*_args, **_kwargs) -> _FakeProcess:
        raise OSError("git missing")

    monkeypatch.setattr(blame_mod.asyncio, "create_subprocess_exec", fake_exec)
    chain = await BlameCollector().collect(tmp_path, "app.py", "repo:1", "snap:1")
    assert chain.diagnostics[0].code == "BLAME_EXEC_ERROR"


async def test_collect_timeout(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n")

    async def fake_exec(*_args, **_kwargs) -> _FakeProcess:
        return _FakeProcess(b"")

    async def fake_wait_for(_awaitable, timeout):
        _awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(blame_mod.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(blame_mod.asyncio, "wait_for", fake_wait_for)
    chain = await BlameCollector().collect(tmp_path, "app.py", "repo:1", "snap:1")
    assert chain.diagnostics[0].code == "BLAME_TIMEOUT"
