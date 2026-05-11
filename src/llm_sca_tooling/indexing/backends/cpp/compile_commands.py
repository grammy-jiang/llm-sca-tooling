"""compile_commands.json parser for C/C++ backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic

__all__ = ["CompileCommand", "CompileCommandsResult", "parse_compile_commands"]


@dataclass(frozen=True)
class CompileCommand:
    directory: Path
    file: str
    command: str | None
    arguments: list[str]
    include_dirs: list[str] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)
    standard: str | None = None


@dataclass(frozen=True)
class CompileCommandsResult:
    records: list[CompileCommand]
    diagnostics: list[IndexingDiagnostic]


def parse_compile_commands(repo_root: Path) -> CompileCommandsResult:
    path = repo_root / "compile_commands.json"
    if not path.exists():
        return CompileCommandsResult(
            [],
            [
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="COMPILE_COMMANDS_MISSING",
                    message="compile_commands.json not found; C/C++ analysis degraded",
                    backend_id="cpp.compile_commands",
                )
            ],
        )
    try:
        data: Any = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError as exc:
        return CompileCommandsResult(
            [],
            [
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.error,
                    code="FILE_PARSE_ERROR",
                    message=f"invalid compile_commands.json: {exc}",
                    file_path="compile_commands.json",
                    backend_id="cpp.compile_commands",
                )
            ],
        )
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        return CompileCommandsResult(
            [],
            [
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.error,
                    code="FILE_PARSE_ERROR",
                    message="invalid compile_commands.json: expected an array of records",
                    file_path="compile_commands.json",
                    backend_id="cpp.compile_commands",
                )
            ],
        )
    records = [_record(repo_root, item) for item in data]
    return CompileCommandsResult(records, [])


def _record(repo_root: Path, item: dict[str, Any]) -> CompileCommand:
    args = item.get("arguments")
    command: str | None
    if not isinstance(args, list):
        command = str(item.get("command", ""))
        args = command.split()
    else:
        command = str(item.get("command")) if item.get("command") else None
        args = [str(arg) for arg in args]
    include_dirs = [arg[2:] for arg in args if arg.startswith("-I") and len(arg) > 2]
    defines = [arg[2:] for arg in args if arg.startswith("-D") and len(arg) > 2]
    standard = next((arg for arg in args if arg.startswith("-std=")), None)
    directory = Path(str(item.get("directory", repo_root)))
    file_path = Path(str(item.get("file", "")))
    if file_path.is_absolute():
        file_rel = str(file_path.relative_to(repo_root)).replace("\\", "/")
    else:
        file_rel = str(file_path).replace("\\", "/")
    return CompileCommand(
        directory, file_rel, command, args, include_dirs, defines, standard
    )
