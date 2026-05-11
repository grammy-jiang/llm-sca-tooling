"""Tests for GitHookInstaller."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from llm_sca_tooling.hardening.git_hooks import GitHookInstaller


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_install_creates_hooks(fake_repo: Path) -> None:
    installer = GitHookInstaller()
    records = installer.install(str(fake_repo))
    assert len(records) == 2
    assert all(r.installed for r in records)
    for name in ("post-commit", "post-checkout"):
        hook = fake_repo / ".git" / "hooks" / name
        assert hook.exists()
        assert hook.stat().st_mode & stat.S_IXUSR


def test_install_is_idempotent(fake_repo: Path) -> None:
    installer = GitHookInstaller()
    installer.install(str(fake_repo))
    records = installer.install(str(fake_repo))
    assert all(r.installed for r in records)


def test_uninstall_removes_hooks(fake_repo: Path) -> None:
    installer = GitHookInstaller()
    installer.install(str(fake_repo))
    records = installer.uninstall(str(fake_repo))
    assert all(not r.installed for r in records)
    for name in ("post-commit", "post-checkout"):
        assert not (fake_repo / ".git" / "hooks" / name).exists()


def test_is_installed(fake_repo: Path) -> None:
    installer = GitHookInstaller()
    assert not installer.is_installed(str(fake_repo), "post-commit")
    installer.install(str(fake_repo))
    assert installer.is_installed(str(fake_repo), "post-commit")


def test_install_records_in_ledger(fake_repo: Path) -> None:
    ledger: list[object] = []
    installer = GitHookInstaller(ledger=ledger.append)
    installer.install(str(fake_repo))
    assert len(ledger) == 2
