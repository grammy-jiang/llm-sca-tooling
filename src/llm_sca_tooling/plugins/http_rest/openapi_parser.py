"""Small OpenAPI/Swagger parser for static route extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.plugins.capability import ConfidenceLevel, InterfaceKind, OperationType
from llm_sca_tooling.plugins.http_rest.url_normalizer import normalize_url_pattern
from llm_sca_tooling.plugins.interface_record import InterfaceOperation, InterfaceRecord, interface_id_for, operation_id_for
from llm_sca_tooling.schemas.provenance import Provenance

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def parse_openapi_file(path: Path, *, repo_id: str, plugin_id: str, plugin_version: str, provenance: Provenance, snapshot_id: str) -> list[InterfaceRecord]:
    document = _load_document(path)
    if not document:
        return []
    paths = document.get("paths") if isinstance(document, dict) else None
    if not isinstance(paths, dict):
        return []
    records = []
    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            canonical = normalize_url_pattern(str(raw_path))
            name = f"{method.upper()} {canonical}"
            interface_id = interface_id_for(plugin_id, InterfaceKind.HTTP, name, repo_id)
            op = operation if isinstance(operation, dict) else {}
            parameters = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
            operation_record = InterfaceOperation(
                operation_id=operation_id_for(interface_id, canonical, method.upper()),
                interface_id=interface_id,
                name=canonical,
                operation_type=OperationType.ROUTE,
                http_method=method.upper(),
                path_pattern=canonical,
                input_schema={"parameters": parameters} if parameters else None,
                output_schema={"responses": responses} if responses else None,
                status_codes=[int(code) for code in responses if str(code).isdigit()] or None,
                auth_hints=list((op.get("security") or [{}])[0].keys()) if isinstance(op.get("security"), list) and op.get("security") else None,
                confidence=ConfidenceLevel.PARSER,
                binding_method="openapi",
                metadata={"operation_id": op.get("operationId"), "source": path.name},
            )
            records.append(
                InterfaceRecord(
                    interface_id=interface_id,
                    kind=InterfaceKind.HTTP,
                    plugin_id=plugin_id,
                    plugin_version=plugin_version,
                    interface_name=name,
                    definition_files=[path.name],
                    source_repos=[repo_id],
                    operations=[operation_record],
                    confidence=ConfidenceLevel.PARSER,
                    snapshot_ids={repo_id: snapshot_id},
                    provenance=provenance,
                )
            )
    return records


def _load_document(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return _minimal_yaml_paths(text)


def _minimal_yaml_paths(text: str) -> dict:
    paths: dict[str, dict] = {}
    current_path: str | None = None
    current_method: str | None = None
    for line in text.splitlines():
        path_match = re.match(r"\s{2}(/[^:]+):\s*$", line)
        if path_match:
            current_path = path_match.group(1)
            paths.setdefault(current_path, {})
            continue
        method_match = re.match(r"\s{4}(get|post|put|delete|patch|head|options):\s*$", line, re.I)
        if method_match and current_path:
            current_method = method_match.group(1).lower()
            paths[current_path][current_method] = {}
            continue
        op_match = re.match(r"\s{6}operationId:\s*([A-Za-z0-9_.:-]+)", line)
        if op_match and current_path and current_method:
            paths[current_path][current_method]["operationId"] = op_match.group(1)
    return {"paths": paths}
