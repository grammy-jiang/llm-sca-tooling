"""Pyright LSP availability adapter."""

from __future__ import annotations

import shutil

from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.capability import BackendAvailability

__all__ = ["PyrightAdapter"]


class PyrightAdapter:
    @property
    def backend_id(self) -> str:
        return "python.pyright"

    async def check_availability(
        self, context: IndexingContext | None = None
    ) -> BackendAvailability:
        tool = shutil.which("pyright-langserver") or shutil.which("pyright")
        configured = bool(
            context
            and (
                (context.repo_root / "pyrightconfig.json").exists()
                or (context.repo_root / "pyproject.toml").exists()
            )
        )
        return BackendAvailability(
            backend_id=self.backend_id,
            available=bool(tool and configured),
            tool_path=tool,
            tool_version="unknown" if tool else None,
            missing_deps=[] if tool else ["pyright-langserver"],
            warnings=[] if configured else ["Pyright project configuration not found"],
        )
