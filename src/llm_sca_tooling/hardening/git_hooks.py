"""Git hook installer for post-commit and post-checkout hooks.

``GitHookInstaller`` installs and removes hooks in any registered git
repository.  Installation is recorded in the operational ledger.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["GitHookInstaller", "HookInstallRecord"]

logger = get_logger(__name__)

_POST_COMMIT_BODY = """\
#!/usr/bin/env sh
# Installed by llm-sca-tooling – do not edit manually.
llm-sca-tooling graph-update --repo . || true
"""

_POST_CHECKOUT_BODY = """\
#!/usr/bin/env sh
# Installed by llm-sca-tooling – do not edit manually.
llm-sca-tooling graph-update --repo . || true
"""

_MARKER = "# Installed by llm-sca-tooling"


class HookInstallRecord:
    def __init__(self, repo_path: str, hook_name: str, installed: bool) -> None:
        self.repo_path = repo_path
        self.hook_name = hook_name
        self.installed = installed


class GitHookInstaller:
    """Install and remove llm-sca-tooling git hooks.

    Args:
        ledger: Optional callable for persisting ``HookInstallRecord`` objects.
    """

    def __init__(self, ledger: Any | None = None) -> None:
        self._ledger = ledger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, repo_path: str) -> list[HookInstallRecord]:
        """Install post-commit and post-checkout hooks in *repo_path*.

        Returns one record per hook.  Existing hooks not owned by this
        tool are left unchanged and recorded as skipped.
        """
        hooks_dir = self._hooks_dir(repo_path)
        if not hooks_dir.exists():
            hooks_dir.mkdir(parents=True, exist_ok=True)

        records: list[HookInstallRecord] = []
        for name, body in [
            ("post-commit", _POST_COMMIT_BODY),
            ("post-checkout", _POST_CHECKOUT_BODY),
        ]:
            record = self._install_hook(hooks_dir, name, body, repo_path)
            records.append(record)
            if self._ledger is not None:
                self._ledger(record)
        return records

    def uninstall(self, repo_path: str) -> list[HookInstallRecord]:
        """Remove hooks installed by this tool from *repo_path*."""
        hooks_dir = self._hooks_dir(repo_path)
        records: list[HookInstallRecord] = []
        for name in ("post-commit", "post-checkout"):
            record = self._uninstall_hook(hooks_dir, name, repo_path)
            records.append(record)
            if self._ledger is not None:
                self._ledger(record)
        return records

    def is_installed(self, repo_path: str, hook_name: str) -> bool:
        """Return ``True`` if *hook_name* is installed by this tool."""
        hook_path = self._hooks_dir(repo_path) / hook_name
        if not hook_path.exists():
            return False
        return _MARKER in hook_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _install_hook(
        self,
        hooks_dir: Path,
        name: str,
        body: str,
        repo_path: str,
    ) -> HookInstallRecord:
        hook_path = hooks_dir / name
        if hook_path.exists():
            existing = hook_path.read_text(encoding="utf-8")
            if _MARKER in existing:
                logger.debug("Hook %s already installed in %s", name, repo_path)
                return HookInstallRecord(repo_path, name, installed=True)
            logger.warning(
                "Hook %s exists and is not owned by llm-sca-tooling; skipping",
                name,
            )
            return HookInstallRecord(repo_path, name, installed=False)

        hook_path.write_text(body, encoding="utf-8")
        hook_path.chmod(
            hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
        logger.info("Installed %s hook in %s", name, repo_path)
        return HookInstallRecord(repo_path, name, installed=True)

    def _uninstall_hook(
        self, hooks_dir: Path, name: str, repo_path: str
    ) -> HookInstallRecord:
        hook_path = hooks_dir / name
        if not hook_path.exists():
            return HookInstallRecord(repo_path, name, installed=False)
        content = hook_path.read_text(encoding="utf-8")
        if _MARKER not in content:
            logger.warning(
                "Hook %s in %s not owned by this tool; leaving intact",
                name,
                repo_path,
            )
            return HookInstallRecord(repo_path, name, installed=False)
        hook_path.unlink()
        logger.info("Uninstalled %s hook from %s", name, repo_path)
        return HookInstallRecord(repo_path, name, installed=False)

    @staticmethod
    def _hooks_dir(repo_path: str) -> Path:
        return Path(repo_path) / ".git" / "hooks"
