"""SARIF v2.1.0 parser and URI resolver."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import orjson
from jsonschema import ValidationError, validate

from llm_sca_tooling.sarif.models import (
    SarifArtifactLocation,
    SarifLocation,
    SarifLog,
    SarifPhysicalLocation,
    SarifRegion,
    SarifReportingDescriptor,
    SarifResult,
    SarifRun,
    SarifTool,
    SarifToolComponent,
)

__all__ = [
    "SarifParseError",
    "SarifVersionError",
    "parse_sarif_bytes",
    "parse_sarif_file",
    "resolve_artifact_uri",
]

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "runs"],
    "properties": {
        "version": {"type": "string"},
        "runs": {"type": "array"},
        "$schema": {"type": "string"},
    },
}


class SarifParseError(ValueError):
    """Raised for malformed or schema-invalid SARIF input."""


class SarifVersionError(SarifParseError):
    """Raised when the SARIF version is unsupported."""


def parse_sarif_file(path: Path, *, repo_root: Path | None = None) -> SarifLog:
    return parse_sarif_bytes(path.read_bytes(), repo_root=repo_root)


def parse_sarif_bytes(data: bytes, *, repo_root: Path | None = None) -> SarifLog:
    try:
        raw: Any = orjson.loads(data)
    except orjson.JSONDecodeError as exc:
        raise SarifParseError(f"malformed SARIF JSON: {exc}") from exc
    try:
        validate(raw, _SCHEMA)
    except ValidationError as exc:
        raise SarifParseError(f"invalid SARIF shape: {exc.message}") from exc
    if not isinstance(raw, dict):
        raise SarifParseError("SARIF root must be an object")
    version = raw.get("version")
    if version != "2.1.0":
        raise SarifVersionError(f"unsupported SARIF version: {version!r}")
    runs = [_parse_run(run, repo_root) for run in _list(raw.get("runs"))]
    return SarifLog(
        version="2.1.0",
        schema_uri=raw.get("$schema") if isinstance(raw.get("$schema"), str) else None,
        runs=runs,
    )


def _parse_run(raw: object, repo_root: Path | None) -> SarifRun:
    item = raw if isinstance(raw, dict) else {}
    tool = _parse_tool(_dict(item.get("tool")))
    bases = {
        str(key): _artifact_base_uri(value)
        for key, value in _dict(item.get("originalUriBaseIds")).items()
    }
    results = [
        _parse_result(result, tool.driver.rules, bases, repo_root)
        for result in _list(item.get("results"))
    ]
    invocations = _list(item.get("invocations"))
    first_invocation = _dict(invocations[0]) if invocations else {}
    return SarifRun(
        tool=tool,
        results=results,
        original_uri_base_ids=bases,
        invocation_successful=bool(first_invocation.get("executionSuccessful", True)),
        invocation_exit_code=(
            int(first_invocation["exitCode"])
            if isinstance(first_invocation.get("exitCode"), int)
            else None
        ),
    )


def _parse_tool(raw: dict[str, Any]) -> SarifTool:
    return SarifTool(
        driver=_parse_component(_dict(raw.get("driver"))),
        extensions=[_parse_component(item) for item in _list(raw.get("extensions"))],
    )


def _parse_component(raw: dict[str, Any]) -> SarifToolComponent:
    return SarifToolComponent(
        name=str(raw.get("name") or "unknown"),
        version=raw.get("version") if isinstance(raw.get("version"), str) else None,
        semantic_version=(
            raw.get("semanticVersion")
            if isinstance(raw.get("semanticVersion"), str)
            else None
        ),
        guid=raw.get("guid") if isinstance(raw.get("guid"), str) else None,
        rules=[_parse_rule(item) for item in _list(raw.get("rules"))],
    )


def _parse_rule(raw: dict[str, Any]) -> SarifReportingDescriptor:
    default_config = _dict(raw.get("defaultConfiguration"))
    return SarifReportingDescriptor(
        id=str(raw.get("id") or "unknown"),
        name=raw.get("name") if isinstance(raw.get("name"), str) else None,
        short_description=_message_text(raw.get("shortDescription")),
        full_description=_message_text(raw.get("fullDescription")),
        help_uri=raw.get("helpUri") if isinstance(raw.get("helpUri"), str) else None,
        default_level=(
            default_config.get("level")
            if isinstance(default_config.get("level"), str)
            else None
        ),
        properties=_dict(raw.get("properties")),
    )


def _parse_result(
    raw: object,
    rules: list[SarifReportingDescriptor],
    bases: dict[str, str],
    repo_root: Path | None,
) -> SarifResult:
    item = raw if isinstance(raw, dict) else {}
    rule_id = item.get("ruleId") if isinstance(item.get("ruleId"), str) else None
    rule_index = (
        item.get("ruleIndex") if isinstance(item.get("ruleIndex"), int) else None
    )
    if rule_id is None and rule_index is not None and 0 <= rule_index < len(rules):
        rule_id = rules[rule_index].id
    return SarifResult(
        rule_id=rule_id,
        rule_index=rule_index,
        level=item.get("level") if isinstance(item.get("level"), str) else None,
        message=_message_text(item.get("message")) or "",
        locations=[
            _parse_location(location, bases, repo_root)
            for location in _list(item.get("locations"))
        ],
        related_locations=[
            _parse_location(location, bases, repo_root)
            for location in _list(item.get("relatedLocations"))
        ],
        baseline_state=(
            item.get("baselineState")
            if isinstance(item.get("baselineState"), str)
            else None
        ),
        fingerprints=_str_map(item.get("fingerprints")),
        partial_fingerprints=_str_map(item.get("partialFingerprints")),
        suppressions=[
            _dict(suppression) for suppression in _list(item.get("suppressions"))
        ],
        properties=_dict(item.get("properties")),
    )


def _parse_location(
    raw: object, bases: dict[str, str], repo_root: Path | None
) -> SarifLocation:
    item = raw if isinstance(raw, dict) else {}
    physical = _dict(item.get("physicalLocation"))
    parsed_physical = None
    if physical:
        artifact = _dict(physical.get("artifactLocation"))
        uri = artifact.get("uri") if isinstance(artifact.get("uri"), str) else None
        base_id = (
            artifact.get("uriBaseId")
            if isinstance(artifact.get("uriBaseId"), str)
            else None
        )
        parsed_physical = SarifPhysicalLocation(
            artifact_location=SarifArtifactLocation(
                uri=uri,
                uri_base_id=base_id,
                index=(
                    artifact.get("index")
                    if isinstance(artifact.get("index"), int)
                    else None
                ),
                resolved_path=resolve_artifact_uri(uri, base_id, bases, repo_root),
            ),
            region=_parse_region(_dict(physical.get("region"))),
        )
    return SarifLocation(
        physical_location=parsed_physical,
        message=_message_text(item.get("message")),
    )


def _parse_region(raw: dict[str, Any]) -> SarifRegion | None:
    if not raw:
        return None
    snippet = _dict(raw.get("snippet"))
    return SarifRegion(
        start_line=_int(raw.get("startLine")),
        start_column=_int(raw.get("startColumn")),
        end_line=_int(raw.get("endLine")),
        end_column=_int(raw.get("endColumn")),
        byte_offset=_int(raw.get("byteOffset")),
        byte_length=_int(raw.get("byteLength")),
        snippet_text=(
            snippet.get("text") if isinstance(snippet.get("text"), str) else None
        ),
    )


def resolve_artifact_uri(
    uri: str | None,
    uri_base_id: str | None,
    bases: dict[str, str],
    repo_root: Path | None,
) -> str | None:
    if not uri:
        return None
    original_uri = uri
    candidate = uri
    if uri_base_id and uri_base_id in bases:
        candidate = bases[uri_base_id].rstrip("/") + "/" + uri.lstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme == "file":
        candidate = unquote(parsed.path)
    elif parsed.scheme and parsed.scheme not in {"file"}:
        return None
    path = Path(candidate)
    if path.is_absolute() and repo_root:
        try:
            return str(path.resolve().relative_to(repo_root.resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            if not Path(original_uri).is_absolute():
                return original_uri.replace("\\", "/")
            return None
    return str(path).replace("\\", "/")


def _artifact_base_uri(raw: object) -> str:
    item = _dict(raw)
    location = (
        _dict(item.get("uri"))
        if "uri" in item and not isinstance(item.get("uri"), str)
        else item
    )
    uri = location.get("uri")
    return str(uri) if uri is not None else ""


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _message_text(value: object) -> str | None:
    item = _dict(value)
    text = item.get("text") or item.get("markdown")
    return text if isinstance(text, str) else None


def _str_map(value: object) -> dict[str, str]:
    item = _dict(value)
    return {str(key): str(raw) for key, raw in item.items()}
