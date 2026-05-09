"""compile_commands.json parser."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class CompileCommand(StrictBaseModel):
    directory: str
    file: str
    command: str | None = None
    arguments: list[str] = Field(default_factory=list)
    repo_relative_file: str
    include_dirs: list[str] = Field(default_factory=list)
    defines: list[str] = Field(default_factory=list)
    standard: str | None = None


class CompileCommands:
    def load(self, repo_root: Path) -> tuple[list[CompileCommand], list[str]]:
        path = repo_root / "compile_commands.json"
        diagnostics: list[str] = []
        if not path.exists():
            return [], ["COMPILE_COMMANDS_MISSING"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        commands = []
        for entry in payload:
            raw_file = Path(entry["file"])
            abs_file = raw_file if raw_file.is_absolute() else Path(entry.get("directory", repo_root)) / raw_file
            rel = abs_file.resolve().relative_to(repo_root.resolve()).as_posix()
            args = entry.get("arguments") or str(entry.get("command", "")).split()
            commands.append(
                CompileCommand(
                    directory=str(entry.get("directory", repo_root)),
                    file=str(entry["file"]),
                    command=entry.get("command"),
                    arguments=args,
                    repo_relative_file=rel,
                    include_dirs=[arg[2:] for arg in args if arg.startswith("-I")],
                    defines=[arg[2:] for arg in args if arg.startswith("-D")],
                    standard=next((arg for arg in args if arg.startswith("-std=")), None),
                )
            )
        return commands, diagnostics
