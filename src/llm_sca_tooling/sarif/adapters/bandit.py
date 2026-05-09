"""Bandit SARIF adapter with JSON fallback."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from shutil import which

from llm_sca_tooling.sarif.adapters.base import (
    AnalyserAdapterBase,
    AnalyserAvailability,
    ResolvedRuleset,
)
from llm_sca_tooling.sarif.errors import AnalyserUnavailableError
from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.sarif.parser import SarifParser
from llm_sca_tooling.schemas.base import JsonObject


class BanditAdapter(AnalyserAdapterBase):
    adapter_id = "bandit"

    def check_availability(self) -> AnalyserAvailability:
        exe = which("bandit")
        if not exe:
            return AnalyserAvailability(
                analyser_id=self.adapter_id,
                available=False,
                diagnostics=["ANALYSER_UNAVAILABLE:bandit"],
            )
        result = subprocess.run(
            [exe, "--version"], check=False, capture_output=True, text=True, timeout=10
        )
        return AnalyserAvailability(
            analyser_id=self.adapter_id,
            available=True,
            version=(
                (result.stdout or result.stderr).strip().splitlines()[0]
                if (result.stdout or result.stderr).strip()
                else None
            ),
        )

    def run(
        self,
        repo_root: Path,
        *,
        ruleset: ResolvedRuleset | None = None,
        files: list[str] | None = None,
        config: JsonObject | None = None,
    ) -> SarifLog:
        config = config or {}
        availability = self.check_availability()
        if not availability.available:
            raise AnalyserUnavailableError("; ".join(availability.diagnostics))
        target = (
            [str(repo_root / file_path) for file_path in files]
            if files
            else [str(repo_root)]
        )
        with tempfile.NamedTemporaryFile(suffix=".sarif.json", delete=False) as tmp:
            output = Path(tmp.name)
        try:
            cmd = ["bandit", "-r", *target, "-f", "sarif", "-o", str(output)]
            if config.get("tests"):
                cmd.extend(["-t", ",".join(config["tests"])])
            if config.get("skips"):
                cmd.extend(["-s", ",".join(config["skips"])])
            result = subprocess.run(
                cmd,
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=int(config.get("timeout_seconds", 60)),
            )
            if output.exists() and output.stat().st_size:
                return SarifParser().parse_file(output, repo_root=repo_root)
            if result.returncode not in {0, 1}:
                return self._run_json_fallback(repo_root, target, config)
            return SarifParser().parse_obj(_empty_sarif(), repo_root=repo_root)
        except subprocess.TimeoutExpired as exc:
            raise AnalyserUnavailableError("ANALYSER_TIMEOUT:bandit") from exc
        finally:
            output.unlink(missing_ok=True)

    def _run_json_fallback(
        self, repo_root: Path, target: list[str], config: JsonObject
    ) -> SarifLog:
        result = subprocess.run(
            ["bandit", "-r", *target, "-f", "json"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=int(config.get("timeout_seconds", 60)),
        )
        if result.returncode not in {0, 1}:
            raise AnalyserUnavailableError(f"ANALYSER_ERROR:bandit:{result.returncode}")
        return SarifParser().parse_obj(
            bandit_json_to_sarif(json.loads(result.stdout or "{}")), repo_root=repo_root
        )


def bandit_json_to_sarif(payload: dict) -> dict:
    rules = {}
    results = []
    for item in payload.get("results") or []:
        rule_id = item.get("test_id") or "B000"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": item.get("test_name") or rule_id,
                "shortDescription": {"text": item.get("issue_text") or rule_id},
                "properties": {
                    "issue_severity": item.get("issue_severity"),
                    "issue_confidence": item.get("issue_confidence"),
                    "tags": ["security"],
                },
            },
        )
        results.append(
            {
                "ruleId": rule_id,
                "level": "warning",
                "message": {"text": item.get("issue_text") or ""},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": item.get("filename")},
                            "region": {"startLine": item.get("line_number") or 1},
                        }
                    }
                ],
                "properties": {
                    "issue_severity": item.get("issue_severity"),
                    "issue_confidence": item.get("issue_confidence"),
                    "analyser_synthetic_sarif": True,
                },
            }
        )
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Bandit", "rules": list(rules.values())}},
                "results": results,
            }
        ],
    }


def _empty_sarif() -> dict:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Bandit", "rules": []}}, "results": []}],
    }
