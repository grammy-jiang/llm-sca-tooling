"""Optional CodeQL adapter gated off by default."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sarif.adapters.base import (
    AnalyserAdapterBase,
    AnalyserAvailability,
    ResolvedRuleset,
)
from llm_sca_tooling.sarif.errors import AnalyserUnavailableError
from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.schemas.base import JsonObject

CODEQL_BACKEND_ENABLED = False


class CodeQLAdapter(AnalyserAdapterBase):
    adapter_id = "codeql"

    def __init__(self, *, enabled: bool = CODEQL_BACKEND_ENABLED) -> None:
        self.enabled = enabled

    def check_availability(self) -> AnalyserAvailability:
        if not self.enabled:
            return AnalyserAvailability(
                analyser_id=self.adapter_id,
                available=False,
                diagnostics=["CODEQL_BACKEND_DISABLED"],
            )
        return AnalyserAvailability(
            analyser_id=self.adapter_id,
            available=False,
            diagnostics=["CODEQL_EXECUTION_NOT_IMPLEMENTED"],
        )

    def run(
        self,
        repo_root: Path,
        *,
        ruleset: ResolvedRuleset | None = None,
        files: list[str] | None = None,
        config: JsonObject | None = None,
    ) -> SarifLog:
        raise AnalyserUnavailableError("; ".join(self.check_availability().diagnostics))
