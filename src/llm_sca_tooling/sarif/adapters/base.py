"""Static analyser adapter contracts."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class AnalyserAvailability(StrictBaseModel):
    analyser_id: str
    available: bool
    version: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class ResolvedRuleset(StrictBaseModel):
    ruleset_id: str
    ruleset_name: str | None = None
    args: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class AnalyserAdapterBase:
    adapter_id: str

    def check_availability(self) -> AnalyserAvailability:
        raise NotImplementedError

    def run(
        self,
        repo_root: Path,
        *,
        ruleset: ResolvedRuleset | None = None,
        files: list[str] | None = None,
        config: JsonObject | None = None,
    ) -> SarifLog:
        raise NotImplementedError
