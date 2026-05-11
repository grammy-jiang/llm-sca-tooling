"""Base contracts for SARIF analyser adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llm_sca_tooling.sarif.models import SarifLog

__all__ = ["AnalyserAvailability", "AnalyserRunResult", "RulesetConfig"]


@dataclass(frozen=True)
class AnalyserAvailability:
    analyser_id: str
    available: bool
    tool_path: str | None = None
    tool_version: str | None = None
    missing_deps: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RulesetConfig:
    entries: list[str] = field(default_factory=list)
    offline: bool = True
    timeout_ms: int = 30_000


@dataclass(frozen=True)
class AnalyserRunResult:
    sarif_log: SarifLog | None
    diagnostics: list[str] = field(default_factory=list)
    exit_code: int | None = None
    raw_output_path: Path | None = None
