"""SARIF v2.1.0 parser with repo-relative URI resolution."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from llm_sca_tooling.sarif.errors import SarifParseError, SarifVersionError
from llm_sca_tooling.sarif.models import (
    SarifArtifact,
    SarifArtifactLocation,
    SarifCodeFlow,
    SarifFix,
    SarifInvocation,
    SarifLocation,
    SarifLog,
    SarifLogicalLocation,
    SarifNotification,
    SarifPhysicalLocation,
    SarifRegion,
    SarifReportingConfiguration,
    SarifReportingDescriptor,
    SarifReportingDescriptorReference,
    SarifResult,
    SarifRun,
    SarifRunAutomationDetails,
    SarifSuppression,
    SarifThreadFlow,
    SarifThreadFlowLocation,
    SarifTool,
    SarifToolComponent,
)


class SarifParser:
    def parse_file(
        self, path: str | Path, *, repo_root: str | Path | None = None
    ) -> SarifLog:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise SarifParseError(str(exc)) from exc
        return self.parse_text(raw, repo_root=repo_root)

    def parse_text(self, text: str, *, repo_root: str | Path | None = None) -> SarifLog:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SarifParseError(f"malformed SARIF JSON: {exc}") from exc
        return self.parse_obj(payload, repo_root=repo_root)

    def parse_obj(
        self, payload: dict[str, Any], *, repo_root: str | Path | None = None
    ) -> SarifLog:
        if not isinstance(payload, dict):
            raise SarifParseError("SARIF payload must be a JSON object")
        version = payload.get("version")
        if version != "2.1.0":
            raise SarifVersionError(f"unsupported SARIF version: {version!r}")
        diagnostics = [
            f"unknown_top_level:{key}"
            for key in sorted(set(payload) - {"version", "$schema", "runs"})
        ]
        try:
            runs = [
                self._run(
                    item, repo_root=Path(repo_root).resolve() if repo_root else None
                )
                for item in payload.get("runs") or []
            ]
            return SarifLog(
                version="2.1.0",
                schema_uri=payload.get("$schema"),
                runs=runs,
                diagnostics=diagnostics,
            )
        except ValidationError as exc:
            raise SarifParseError(str(exc)) from exc

    def _run(self, raw: dict[str, Any], *, repo_root: Path | None) -> SarifRun:
        bases = {
            key: ((value.get("uri") if isinstance(value, dict) else None) or "")
            for key, value in (raw.get("originalUriBaseIds") or {}).items()
        }
        artifacts = [
            self._artifact(item, repo_root=repo_root, bases=bases)
            for item in raw.get("artifacts") or []
        ]
        tool = self._tool(raw.get("tool") or {})
        return SarifRun(
            tool=tool,
            results=[
                self._result(item, repo_root=repo_root, bases=bases)
                for item in raw.get("results") or []
            ],
            artifacts=artifacts,
            logical_locations=[
                self._logical_location(item)
                for item in raw.get("logicalLocations") or []
            ],
            invocations=[
                self._invocation(item, repo_root=repo_root, bases=bases)
                for item in raw.get("invocations") or []
            ],
            automation_details=self._automation(raw.get("automationDetails")),
            baseline_guid=raw.get("baselineGuid"),
            original_uri_base_ids=bases,
            properties=raw.get("properties") or {},
        )

    def _tool(self, raw: dict[str, Any]) -> SarifTool:
        return SarifTool(
            driver=self._component(raw.get("driver") or {"name": "unknown"}),
            extensions=[self._component(item) for item in raw.get("extensions") or []],
        )

    def _component(self, raw: dict[str, Any]) -> SarifToolComponent:
        return SarifToolComponent(
            name=raw.get("name") or "unknown",
            version=raw.get("version"),
            semantic_version=raw.get("semanticVersion"),
            guid=raw.get("guid"),
            rules=[self._rule(item) for item in raw.get("rules") or []],
            notifications=[self._rule(item) for item in raw.get("notifications") or []],
        )

    def _rule(self, raw: dict[str, Any]) -> SarifReportingDescriptor:
        cfg = raw.get("defaultConfiguration")
        return SarifReportingDescriptor(
            id=str(raw.get("id") or raw.get("name") or "unknown"),
            name=raw.get("name"),
            short_description=_message_text(raw.get("shortDescription")),
            full_description=_message_text(raw.get("fullDescription")),
            help_uri=raw.get("helpUri"),
            default_configuration=(
                SarifReportingConfiguration(
                    enabled=cfg.get("enabled", True),
                    level=cfg.get("level"),
                    rank=cfg.get("rank"),
                )
                if isinstance(cfg, dict)
                else None
            ),
            properties=raw.get("properties") or {},
        )

    def _result(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifResult:
        return SarifResult(
            rule_id=raw.get("ruleId"),
            rule_index=raw.get("ruleIndex"),
            level=raw.get("level"),
            message=_message_text(raw.get("message")) or "",
            locations=[
                self._location(item, repo_root=repo_root, bases=bases)
                for item in raw.get("locations") or []
            ],
            related_locations=[
                self._location(item, repo_root=repo_root, bases=bases)
                for item in raw.get("relatedLocations") or []
            ],
            code_flows=[
                self._code_flow(item, repo_root=repo_root, bases=bases)
                for item in raw.get("codeFlows") or []
            ],
            fixes=[
                self._fix(item, repo_root=repo_root, bases=bases)
                for item in raw.get("fixes") or []
            ],
            suppressions=[
                SarifSuppression(
                    kind=item.get("kind") or "external",
                    status=item.get("status"),
                    justification=item.get("justification"),
                )
                for item in raw.get("suppressions") or []
            ],
            baseline_state=raw.get("baselineState"),
            fingerprints={
                str(k): str(v) for k, v in (raw.get("fingerprints") or {}).items()
            },
            partial_fingerprints={
                str(k): str(v)
                for k, v in (raw.get("partialFingerprints") or {}).items()
            },
            work_item_uris=[str(item) for item in raw.get("workItemUris") or []],
            properties=raw.get("properties") or {},
        )

    def _location(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifLocation:
        physical = raw.get("physicalLocation")
        return SarifLocation(
            physical_location=(
                self._physical_location(physical, repo_root=repo_root, bases=bases)
                if isinstance(physical, dict)
                else None
            ),
            logical_locations=[
                self._logical_location(item)
                for item in raw.get("logicalLocations") or []
            ],
            message=_message_text(raw.get("message")),
        )

    def _physical_location(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifPhysicalLocation:
        return SarifPhysicalLocation(
            artifact_location=self._artifact_location(
                raw.get("artifactLocation") or {}, repo_root=repo_root, bases=bases
            ),
            region=self._region(raw.get("region")),
        )

    def _artifact_location(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifArtifactLocation:
        uri = raw.get("uri")
        base_id = raw.get("uriBaseId")
        resolved = _resolve_uri(uri, base_id, bases, repo_root)
        return SarifArtifactLocation(
            uri=uri,
            uri_base_id=base_id,
            index=raw.get("index"),
            resolved_path=resolved,
            unresolvable=bool(uri and not resolved),
        )

    def _region(self, raw: dict[str, Any] | None) -> SarifRegion | None:
        if not isinstance(raw, dict):
            return None
        snippet = raw.get("snippet") if isinstance(raw.get("snippet"), dict) else {}
        return SarifRegion(
            start_line=raw.get("startLine"),
            start_column=raw.get("startColumn"),
            end_line=raw.get("endLine") or raw.get("startLine"),
            end_column=raw.get("endColumn"),
            byte_offset=raw.get("byteOffset"),
            byte_length=raw.get("byteLength"),
            snippet_text=snippet.get("text"),
        )

    def _logical_location(self, raw: dict[str, Any]) -> SarifLogicalLocation:
        return SarifLogicalLocation(
            name=raw.get("name"),
            fully_qualified_name=raw.get("fullyQualifiedName"),
            kind=raw.get("kind"),
            properties=raw.get("properties") or {},
        )

    def _code_flow(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifCodeFlow:
        return SarifCodeFlow(
            message=_message_text(raw.get("message")),
            thread_flows=[
                SarifThreadFlow(
                    locations=[
                        self._thread_flow_location(
                            item, repo_root=repo_root, bases=bases
                        )
                        for item in tf.get("locations") or []
                    ]
                )
                for tf in raw.get("threadFlows") or []
            ],
        )

    def _thread_flow_location(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifThreadFlowLocation:
        loc = raw.get("location")
        return SarifThreadFlowLocation(
            location=(
                self._location(loc, repo_root=repo_root, bases=bases)
                if isinstance(loc, dict)
                else None
            ),
            kinds=raw.get("kinds") or [],
            state=raw.get("state") or {},
        )

    def _fix(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifFix:
        return SarifFix(
            description=_message_text(raw.get("description")), artifact_changes=[]
        )

    def _artifact(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifArtifact:
        return SarifArtifact(
            location=self._artifact_location(
                raw.get("location") or {}, repo_root=repo_root, bases=bases
            ),
            parent_index=raw.get("parentIndex"),
            length=raw.get("length"),
            mime_type=raw.get("mimeType"),
        )

    def _invocation(
        self, raw: dict[str, Any], *, repo_root: Path | None, bases: dict[str, str]
    ) -> SarifInvocation:
        cwd = raw.get("workingDirectory")
        return SarifInvocation(
            tool_execution_successful=raw.get("executionSuccessful"),
            exit_code=raw.get("exitCode"),
            start_time_utc=raw.get("startTimeUtc"),
            end_time_utc=raw.get("endTimeUtc"),
            working_directory=(
                self._artifact_location(cwd, repo_root=repo_root, bases=bases)
                if isinstance(cwd, dict)
                else None
            ),
            tool_execution_notifications=[
                SarifNotification(
                    message=_message_text(item.get("message")) or "",
                    level=item.get("level"),
                    associated_rule=self._rule_ref(item.get("associatedRule")),
                )
                for item in raw.get("toolExecutionNotifications") or []
            ],
        )

    def _rule_ref(
        self, raw: dict[str, Any] | None
    ) -> SarifReportingDescriptorReference | None:
        return (
            SarifReportingDescriptorReference(id=raw.get("id"), index=raw.get("index"))
            if isinstance(raw, dict)
            else None
        )

    def _automation(
        self, raw: dict[str, Any] | None
    ) -> SarifRunAutomationDetails | None:
        return (
            SarifRunAutomationDetails(id=raw.get("id"), guid=raw.get("guid"))
            if isinstance(raw, dict)
            else None
        )


def _message_text(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return raw.get("text") or raw.get("markdown")
    return str(raw)


def _resolve_uri(
    uri: str | None, base_id: str | None, bases: dict[str, str], repo_root: Path | None
) -> str | None:
    if not uri:
        return None
    decoded = unquote(uri)
    parsed = urlparse(decoded)
    if parsed.scheme == "file":
        decoded = parsed.path
    elif parsed.scheme and parsed.scheme not in {"file"}:
        return None
    if base_id and base_id in bases and not Path(decoded).is_absolute():
        decoded = f"{bases[base_id].rstrip('/')}/{decoded}"
        if decoded.startswith("file://"):
            decoded = urlparse(decoded).path
    path = Path(decoded)
    if path.is_absolute():
        if repo_root:
            try:
                return path.resolve().relative_to(repo_root).as_posix()
            except ValueError:
                return None
        return None
    normalized = PurePosixPath(decoded)
    if any(part in {"", ".", ".."} for part in normalized.parts):
        return None
    return normalized.as_posix()


parse_sarif_file = SarifParser().parse_file
parse_sarif_text = SarifParser().parse_text
