"""Scope derivation and event filtering for dynamic traces."""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

from llm_sca_tooling.traces.models import ScopeFilter


def derive_scope_filter(
    *,
    suspects: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    default_file: str | None = None,
    max_call_depth: int = 10,
) -> ScopeFilter:
    include_files: list[str] = []
    include_modules: list[str] = []
    include_functions: list[str] = []
    for suspect in (suspects or [])[:3]:
        _add_suspect(suspect, include_files, include_modules, include_functions)
    for symbol in changed_symbols or []:
        _add_suspect(symbol, include_files, include_modules, include_functions)
    if not (include_files or include_modules or include_functions) and default_file:
        include_files.append(_repo_style(default_file))
    return ScopeFilter(
        include_modules=include_modules,
        include_files=include_files,
        include_functions=include_functions,
        max_call_depth=max_call_depth,
        derived_from_fl_result=bool(suspects),
        derived_from_changed_symbols=bool(changed_symbols),
    )


def event_is_in_scope(
    *,
    module: str,
    function: str,
    file_path: str,
    scope_filter: ScopeFilter,
) -> bool:
    normalized = _repo_style(file_path)
    if any(
        fnmatch.fnmatch(normalized, pattern)
        for pattern in scope_filter.exclude_patterns
    ):
        return False
    function_path = f"{module}.{function}" if module and function else function
    if scope_filter.include_files and any(
        normalized == path or normalized.endswith(f"/{path}")
        for path in scope_filter.include_files
    ):
        return True
    if scope_filter.include_modules and any(
        module == item or module.startswith(f"{item}.")
        for item in scope_filter.include_modules
    ):
        return True
    return bool(
        scope_filter.include_functions
        and any(
            function == item
            or function_path == item
            or function_path.endswith(f".{item}")
            for item in scope_filter.include_functions
        )
    )


def _add_suspect(
    suspect: str,
    include_files: list[str],
    include_modules: list[str],
    include_functions: list[str],
) -> None:
    value = suspect.strip()
    if not value:
        return
    if value.endswith(".py") or "/" in value:
        include_files.append(_repo_style(value.split(":", 1)[0]))
        if ":" in value:
            include_functions.append(value.split(":", 1)[1])
        return
    if "." in value:
        include_functions.append(value)
        module = value.rsplit(".", 1)[0]
        if module:
            include_modules.append(module)
        return
    include_functions.append(value)


def _repo_style(path: str) -> str:
    return PurePosixPath(Path(path).as_posix()).as_posix().lstrip("./")
