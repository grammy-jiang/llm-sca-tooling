"""Optional CodeQL adapter."""

from __future__ import annotations

import os
import shutil

from llm_sca_tooling.sarif.adapters.base import AnalyserAvailability

__all__ = ["CODEQL_BACKEND_ENABLED", "CodeQLAdapter", "codeql_backend_enabled"]


def codeql_backend_enabled() -> bool:
    return os.environ.get("LLM_SCA_CODEQL_BACKEND_ENABLED") == "1"


CODEQL_BACKEND_ENABLED = codeql_backend_enabled()


class CodeQLAdapter:
    adapter_id = "codeql"

    async def check_availability(self) -> AnalyserAvailability:
        if not codeql_backend_enabled():
            return AnalyserAvailability(
                self.adapter_id,
                False,
                missing_deps=["CODEQL_BACKEND_ENABLED"],
                diagnostics=["CodeQL adapter disabled by default"],
            )
        tool = shutil.which("codeql")
        return AnalyserAvailability(
            self.adapter_id,
            bool(tool),
            tool_path=tool,
            missing_deps=[] if tool else ["codeql"],
        )
