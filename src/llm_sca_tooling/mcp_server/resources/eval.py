"""Evaluation run MCP resource."""

from __future__ import annotations

import hashlib
import json

from llm_sca_tooling.evaluation.models import EvalRun
from llm_sca_tooling.evaluation.store import EvalRunStore
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import _now_ts


class EvalResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://eval/{run_id}",
        name="eval-run",
        description="Stored evaluation run metadata, metrics, and artefact manifest.",
        schema_family="eval-run",
        size_class="artifact-backed",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "eval" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        eval_run_id = parsed.segments[0]
        try:
            run = EvalRunStore(context.workspace.conn).get_eval_run(eval_run_id)
        except KeyError as exc:
            raise ResourceNotFound(f"eval run not found: {eval_run_id}") from exc
        artifacts = _eval_artifacts(context, run)
        payload = {
            "status": "found",
            "eval_run": run.model_dump(mode="json"),
            "artifact_count": len(artifacts),
        }
        return _resource_result(
            uri,
            payload,
            artifacts=artifacts,
            updated_ts=run.end_ts or _now_ts(),
        )


def _resource_result(
    uri: str,
    payload: JsonObject,
    *,
    artifacts: list[ArtifactRef] | None = None,
    updated_ts: str | None = None,
) -> ResourceResult:
    return ResourceResult(
        uri=uri,
        media_type="application/json",
        payload=payload,
        artifact_refs=artifacts or [],
        diagnostics=[],
        etag=_etag(payload),
        updated_ts=updated_ts or _now_ts(),
    )


def _etag(payload: JsonObject) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]


def _eval_artifacts(context: McpRequestContext, run: EvalRun) -> list[ArtifactRef]:
    artifact_ids: set[str] = set()
    manifest = run.artifact_manifest or {}
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict):
        artifact_ids.update(str(value) for value in artifacts.values())
    if run.artefact_manifest_ref:
        artifact_ids.add(run.artefact_manifest_ref)
    refs: list[ArtifactRef] = []
    for artifact_id in sorted(artifact_ids):
        try:
            refs.append(context.workspace.artifacts.get_artifact(artifact_id))
        except Exception:
            continue
    return refs
