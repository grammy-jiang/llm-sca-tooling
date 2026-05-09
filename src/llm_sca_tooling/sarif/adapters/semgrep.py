"""Semgrep SARIF adapter."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from shutil import which

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.sarif.adapters.base import AnalyserAdapterBase, AnalyserAvailability, ResolvedRuleset
from llm_sca_tooling.sarif.adapters.ruleset import resolve_ruleset
from llm_sca_tooling.sarif.errors import AnalyserUnavailableError
from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.sarif.parser import SarifParser


class SemgrepAdapter(AnalyserAdapterBase):
    adapter_id = "semgrep"

    def check_availability(self) -> AnalyserAvailability:
        exe = which("semgrep")
        if not exe:
            return AnalyserAvailability(analyser_id=self.adapter_id, available=False, diagnostics=["ANALYSER_UNAVAILABLE:semgrep"])
        result = subprocess.run([exe, "--version"], check=False, capture_output=True, text=True, timeout=10)
        return AnalyserAvailability(analyser_id=self.adapter_id, available=True, version=(result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr).strip() else None)

    def run(self, repo_root: Path, *, ruleset: ResolvedRuleset | None = None, files: list[str] | None = None, config: JsonObject | None = None) -> SarifLog:
        config = config or {}
        availability = self.check_availability()
        if not availability.available:
            raise AnalyserUnavailableError("; ".join(availability.diagnostics))
        ruleset = ruleset or resolve_ruleset(config.get("ruleset"), repo_root=repo_root, offline=bool(config.get("offline", True)))
        if any(diag.startswith("NETWORK_REQUIRED") for diag in ruleset.diagnostics):
            raise AnalyserUnavailableError("; ".join(ruleset.diagnostics))
        with tempfile.NamedTemporaryFile(suffix=".sarif.json", delete=False) as tmp:
            output = Path(tmp.name)
        try:
            cmd = [
                "semgrep",
                "--sarif",
                "--quiet",
                "--no-rewrite-rule-ids",
                "--output",
                str(output),
                *ruleset.args,
            ]
            for file_path in files or []:
                cmd.extend(["--include", file_path])
            cmd.append(str(repo_root))
            result = subprocess.run(cmd, cwd=repo_root, check=False, capture_output=True, text=True, timeout=int(config.get("timeout_seconds", 60)))
            if result.returncode >= 2:
                raise AnalyserUnavailableError(f"ANALYSER_ERROR:semgrep:{result.returncode}:{_truncate(result.stderr)}")
            return SarifParser().parse_file(output, repo_root=repo_root)
        except subprocess.TimeoutExpired as exc:
            raise AnalyserUnavailableError("ANALYSER_TIMEOUT:semgrep") from exc
        finally:
            output.unlink(missing_ok=True)


def _truncate(value: str, limit: int = 1000) -> str:
    return value[:limit]

