"""Package metadata and JS/TS test-runner detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic

__all__ = ["PackageMetadata", "read_package_metadata"]


@dataclass(frozen=True)
class PackageMetadata:
    name: str | None
    version: str | None
    scripts: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)


def read_package_metadata(repo_root: Path) -> PackageMetadata:
    path = repo_root / "package.json"
    if not path.exists():
        return PackageMetadata(None, None)
    try:
        data: dict[str, Any] = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError as exc:
        return PackageMetadata(
            None,
            None,
            diagnostics=[
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="FILE_PARSE_ERROR",
                    message=f"invalid package.json: {exc}",
                    file_path="package.json",
                    backend_id="typescript.package_meta",
                )
            ],
        )
    return PackageMetadata(
        name=data.get("name") if isinstance(data.get("name"), str) else None,
        version=data.get("version") if isinstance(data.get("version"), str) else None,
        scripts=_str_map(data.get("scripts")),
        dependencies=_str_map(data.get("dependencies")),
        dev_dependencies=_str_map(data.get("devDependencies")),
    )


def _str_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}
