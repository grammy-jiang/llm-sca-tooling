"""Bandit SARIF adapter."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import orjson

from llm_sca_tooling.sarif.adapters.base import (
    AnalyserAvailability,
    AnalyserRunResult,
    RulesetConfig,
)
from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.sarif.parser import parse_sarif_bytes, parse_sarif_file

__all__ = ["BanditAdapter"]


class BanditAdapter:
    adapter_id = "bandit"

    async def check_availability(self) -> AnalyserAvailability:
        tool = shutil.which("bandit")
        if not tool:
            return AnalyserAvailability(self.adapter_id, False, missing_deps=["bandit"])
        version = await _version(tool)
        return AnalyserAvailability(self.adapter_id, True, tool, version)

    async def run(
        self, repo_root: Path, ruleset: RulesetConfig | None = None
    ) -> AnalyserRunResult:
        availability = await self.check_availability()
        if not availability.available or not availability.tool_path:
            return AnalyserRunResult(None, ["BACKEND_UNAVAILABLE: bandit not found"])
        config = ruleset or RulesetConfig()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "bandit.sarif"
            proc = await _run_bandit(
                availability.tool_path,
                repo_root,
                output_path=out,
                output_format="sarif",
                config=config,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=config.timeout_ms / 1000
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return AnalyserRunResult(None, ["ANALYSER_TIMEOUT: bandit timed out"])
            diagnostics = [
                part.decode(errors="replace").strip()[:500]
                for part in (stdout, stderr)
                if part
            ]
            if proc.returncode not in {0, 1} or not out.exists():
                fallback = await _run_json_fallback(
                    availability.tool_path,
                    repo_root,
                    tmp_dir=Path(tmp),
                    config=config,
                    prior_diagnostics=diagnostics,
                    prior_exit_code=proc.returncode,
                )
                if fallback.sarif_log is not None:
                    return fallback
                return AnalyserRunResult(
                    None, fallback.diagnostics or diagnostics, fallback.exit_code
                )
            return AnalyserRunResult(
                parse_sarif_file(out, repo_root=repo_root),
                diagnostics,
                proc.returncode,
                out,
            )


async def _version(tool: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        tool,
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (stdout or stderr).decode(errors="replace").splitlines()[0].strip() or None


async def _run_bandit(
    tool: str,
    repo_root: Path,
    *,
    output_path: Path,
    output_format: str,
    config: RulesetConfig,
) -> asyncio.subprocess.Process:
    cmd = [
        tool,
        "-r",
        str(repo_root),
        "-f",
        output_format,
        "-o",
        str(output_path),
        *_rule_filter_args(config),
    ]
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(repo_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


def _rule_filter_args(config: RulesetConfig) -> list[str]:
    include = [
        entry.upper()
        for entry in config.entries
        if entry.upper().startswith("B") and not entry.startswith(("!", "skip:"))
    ]
    skip = [
        entry.removeprefix("skip:").removeprefix("!").upper()
        for entry in config.entries
        if entry.startswith(("!", "skip:"))
    ]
    args: list[str] = []
    if include:
        args.extend(["-t", ",".join(include)])
    if skip:
        args.extend(["-s", ",".join(skip)])
    return args


async def _run_json_fallback(
    tool: str,
    repo_root: Path,
    *,
    tmp_dir: Path,
    config: RulesetConfig,
    prior_diagnostics: list[str],
    prior_exit_code: int | None,
) -> AnalyserRunResult:
    out = tmp_dir / "bandit.json"
    proc = await _run_bandit(
        tool,
        repo_root,
        output_path=out,
        output_format="json",
        config=config,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=config.timeout_ms / 1000
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return AnalyserRunResult(
            None,
            [*prior_diagnostics, "ANALYSER_TIMEOUT: bandit JSON fallback timed out"],
            prior_exit_code,
        )
    diagnostics = _dedupe_diagnostics(
        *prior_diagnostics,
        *[
            part.decode(errors="replace").strip()[:500]
            for part in (stdout, stderr)
            if part
        ],
    )
    if proc.returncode not in {0, 1} or not out.exists():
        return AnalyserRunResult(None, diagnostics, proc.returncode)
    sarif_log = _bandit_json_to_sarif(out.read_bytes(), repo_root)
    return AnalyserRunResult(sarif_log, diagnostics, proc.returncode, out)


def _bandit_json_to_sarif(data: bytes, repo_root: Path) -> SarifLog:
    raw = orjson.loads(data)
    results = raw.get("results") if isinstance(raw, dict) else []
    rules: dict[str, dict[str, object]] = {}
    sarif_results: list[dict[str, object]] = []
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("test_id") or "BANDIT")
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": item.get("test_name"),
                "properties": {
                    "issue_severity": item.get("issue_severity"),
                    "issue_confidence": item.get("issue_confidence"),
                    "tags": [rule_id],
                },
            },
        )
        sarif_results.append(
            {
                "ruleId": rule_id,
                "level": _bandit_level(item.get("issue_severity")),
                "message": {"text": str(item.get("issue_text") or "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": _repo_relative_path(
                                    item.get("filename"), repo_root
                                )
                            },
                            "region": {
                                "startLine": item.get("line_number"),
                                "startColumn": item.get("col_offset"),
                                "snippet": {"text": item.get("code")},
                            },
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
    return parse_sarif_bytes(
        orjson.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {
                            "driver": {
                                "name": "bandit",
                                "rules": list(rules.values()),
                            }
                        },
                        "results": sarif_results,
                    }
                ],
            }
        ),
        repo_root=repo_root,
    )


def _bandit_level(raw: object) -> str:
    severity = str(raw or "LOW").upper()
    if severity == "HIGH":
        return "error"
    if severity == "MEDIUM":
        return "warning"
    return "note"


def _repo_relative_path(raw: object, repo_root: Path) -> str:
    path = Path(str(raw or ""))
    if path.is_absolute():
        try:
            return path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return path.name
    return path.as_posix().removeprefix("./")


def _dedupe_diagnostics(*items: str) -> list[str]:
    diagnostics: list[str] = []
    for item in items:
        if item and item not in diagnostics:
            diagnostics.append(item)
    return diagnostics
