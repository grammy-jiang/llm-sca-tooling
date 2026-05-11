"""Scope filter engine for trace capture."""

from __future__ import annotations

from llm_sca_tooling.traces.models import ScopeFilter


def derive_scope_from_suspects(
    suspects: list[str],
    *,
    changed_symbol_ids: list[str] | None = None,
) -> ScopeFilter:
    """Derive scope filter from FL suspects (top-3 file suspects)."""
    files = suspects[:3]
    modules = [
        f.replace("/", ".").removesuffix(".py") for f in files if f.endswith(".py")
    ]
    return ScopeFilter(
        include_modules=modules,
        include_files=files,
        derived_from_fl_result=True,
        derived_from_changed_symbols=bool(changed_symbol_ids),
        exclude_patterns=["test_", "_test", "conftest", ".venv", "site-packages"],
    )


def validate_scope(scope: ScopeFilter) -> list[str]:
    """Return list of diagnostics; empty = valid."""
    diagnostics: list[str] = []
    if (
        not scope.include_modules
        and not scope.include_files
        and not scope.include_functions
    ):
        diagnostics.append("scope_empty")
    return diagnostics


def is_in_scope(module: str, file_path: str, scope: ScopeFilter) -> bool:
    """Check if an event is within the scope filter."""
    for pat in scope.exclude_patterns:
        if pat in file_path or pat in module:
            return False
    if not scope.trace_stdlib and _is_stdlib(module):
        return False
    if not scope.trace_third_party and _is_third_party(file_path):
        return False
    if scope.include_modules and any(m in module for m in scope.include_modules):
        return True
    if scope.include_files and any(f in file_path for f in scope.include_files):
        return True
    if scope.include_functions:
        return False
    return bool(scope.include_modules or scope.include_files)


def _is_stdlib(module: str) -> bool:
    stdlib_prefixes = (
        "os",
        "sys",
        "re",
        "io",
        "abc",
        "ast",
        "csv",
        "json",
        "math",
        "time",
        "datetime",
        "pathlib",
        "logging",
        "typing",
        "collections",
        "itertools",
        "functools",
        "contextlib",
        "threading",
        "asyncio",
        "subprocess",
        "tempfile",
        "hashlib",
    )
    return module.split(".")[0] in stdlib_prefixes


def _is_third_party(file_path: str) -> bool:
    return "site-packages" in file_path or ".venv" in file_path
