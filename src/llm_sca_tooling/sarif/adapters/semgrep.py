"""Semgrep SARIF adapter."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_sca_tooling.sarif.adapters.base import (
    AnalyserAvailability,
    AnalyserRunResult,
    RulesetConfig,
)
from llm_sca_tooling.sarif.parser import parse_sarif_file

__all__ = ["SemgrepAdapter"]


class SemgrepAdapter:
    adapter_id = "semgrep"

    async def check_availability(self) -> AnalyserAvailability:
        tool = shutil.which("semgrep")
        if not tool:
            return AnalyserAvailability(
                self.adapter_id, False, missing_deps=["semgrep"]
            )
        version = await _version(tool, "--version")
        return AnalyserAvailability(self.adapter_id, True, tool, version)

    async def run(
        self, repo_root: Path, ruleset: RulesetConfig | None = None
    ) -> AnalyserRunResult:
        availability = await self.check_availability()
        if not availability.available or not availability.tool_path:
            return AnalyserRunResult(None, ["BACKEND_UNAVAILABLE: semgrep not found"])
        config = ruleset or RulesetConfig()
        if config.offline and any(entry.startswith("p/") for entry in config.entries):
            return AnalyserRunResult(
                None, ["NETWORK_REQUIRED: registry rules disabled"]
            )
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "semgrep.sarif"
            cmd = [
                availability.tool_path,
                "--sarif",
                "--no-rewrite-rule-ids",
                "--quiet",
                "--output",
                str(out),
                str(repo_root),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=config.timeout_ms / 1000
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return AnalyserRunResult(None, ["ANALYSER_TIMEOUT: semgrep timed out"])
            diagnostics = _diagnostics(stdout, stderr)
            if proc.returncode not in {0, 1}:
                return AnalyserRunResult(None, diagnostics, proc.returncode)
            return AnalyserRunResult(
                parse_sarif_file(out, repo_root=repo_root),
                diagnostics,
                proc.returncode,
                out,
            )


async def _version(tool: str, flag: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        tool,
        flag,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace").strip() or None


def _diagnostics(stdout: bytes, stderr: bytes) -> list[str]:
    return [
        text
        for text in [
            stdout.decode(errors="replace").strip()[:500],
            stderr.decode(errors="replace").strip()[:500],
        ]
        if text
    ]
