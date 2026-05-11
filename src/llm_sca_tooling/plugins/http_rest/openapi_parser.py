"""OpenAPI and Swagger parser for the HTTP-REST plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
from ruamel.yaml import YAML

from llm_sca_tooling.plugins.http_rest.url_normalizer import normalize_url_path
from llm_sca_tooling.plugins.interface_record import (
    InterfaceKind,
    InterfaceOperation,
    InterfaceRecord,
    OperationParameter,
    OperationType,
    make_interface_id,
    make_operation_id,
)

__all__ = ["parse_openapi_file"]

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def parse_openapi_file(
    path: Path,
    *,
    repo_id: str,
    snapshot_id: str,
    plugin_id: str = "http-rest",
    plugin_version: str = "0.1.0",
) -> list[InterfaceRecord]:
    raw = _load_document(path)
    version = str(raw.get("openapi") or raw.get("swagger") or "")
    if not (version.startswith("3.") or version.startswith("2.")):
        raise ValueError(f"unsupported OpenAPI/Swagger version: {version!r}")
    records: list[InterfaceRecord] = []
    for raw_path, item in _dict(raw.get("paths")).items():
        for method, operation in _dict(item).items():
            if method.lower() not in _HTTP_METHODS:
                continue
            canonical = normalize_url_path(str(raw_path))
            name = f"{method.upper()} {canonical}"
            interface_id = make_interface_id(
                plugin_id, InterfaceKind.http, name, repo_id
            )
            parameters = [
                OperationParameter(
                    name=str(param.get("name") or ""),
                    location=str(param.get("in") or "query"),
                    schema=param.get("schema") if isinstance(param, dict) else None,
                    required=bool(param.get("required", False)),
                )
                for param in _list(_dict(operation).get("parameters"))
                if isinstance(param, dict)
            ]
            op = InterfaceOperation(
                operation_id=make_operation_id(interface_id, canonical, method.upper()),
                interface_id=interface_id,
                name=canonical,
                operation_type=OperationType.route,
                http_method=method.upper(),
                path_pattern=canonical,
                parameters=parameters,
                status_codes=[
                    int(code)
                    for code in _dict(_dict(operation).get("responses"))
                    if str(code).isdigit()
                ],
                confidence="parser",
                binding_method="openapi",
            )
            records.append(
                InterfaceRecord(
                    interface_id=interface_id,
                    kind=InterfaceKind.http,
                    plugin_id=plugin_id,
                    plugin_version=plugin_version,
                    interface_name=name,
                    version=version,
                    definition_files=[path.name],
                    source_repos=[repo_id],
                    operations=[op],
                    confidence="parser",
                    snapshot_ids={repo_id: snapshot_id},
                    provenance={"source": "openapi"},
                )
            )
    return records


def _load_document(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if path.suffix.lower() == ".json":
        parsed = orjson.loads(data)
    else:
        parsed = YAML(typ="safe").load(data.decode())
    return parsed if isinstance(parsed, dict) else {}


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
