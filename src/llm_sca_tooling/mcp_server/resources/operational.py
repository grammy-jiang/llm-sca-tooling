"""Operational, governance, readiness, and incident MCP resource handlers."""

from __future__ import annotations

from llm_sca_tooling.governance.permissions import PermissionProfileLoader
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.mcp_server.resources.core import _resource_result
from llm_sca_tooling.schemas.base import SCHEMA_VERSION
from llm_sca_tooling.storage.errors import RunNotFoundError

# ── code-intelligence://runs/{run_id} ───────────────────────────────────────


class RunRecordResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://runs/{run_id}",
        name="run-record",
        description="Full run record for the given run_id, without events.",
        schema_family="run-record",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "runs"
            and len(parsed.segments) == 1
            and parsed.segments[0] != "harness-condition"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        run_id = parsed.segments[0]
        try:
            view = context.workspace.operations.get_run(run_id)
        except RunNotFoundError as exc:
            raise ResourceNotFound(str(exc)) from exc
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "run": view.run.model_dump(mode="json"),
            },
        )


# ── code-intelligence://runs/{run_id}/harness-condition ─────────────────────


class RunHarnessConditionResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://runs/{run_id}/harness-condition",
        name="run-harness-condition",
        description="Harness condition sheet for the given run_id.",
        schema_family="harness-condition",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "runs"
            and len(parsed.segments) == 2
            and parsed.segments[1] == "harness-condition"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        run_id = parsed.segments[0]
        try:
            view = context.workspace.operations.get_run(run_id)
        except RunNotFoundError as exc:
            raise ResourceNotFound(str(exc)) from exc

        hc_id = view.run.harness_condition_id
        try:
            condition = context.workspace.operations.get_harness_condition(hc_id)
        except RunNotFoundError as exc:
            raise ResourceNotFound(
                f"harness condition {hc_id} for run {run_id} not found"
            ) from exc

        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "harness_condition": condition.model_dump(mode="json"),
            },
        )


# ── code-intelligence://operations/{repo}/ledger ────────────────────────────


class OperationsLedgerResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://operations/{repo}/ledger",
        name="operations-ledger",
        description="Operational record ledger for the given repository.",
        schema_family="operational-ledger",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "operations"
            and len(parsed.segments) == 2
            and parsed.segments[1] == "ledger"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo_id = parsed.segments[0]
        records = context.workspace.operations.query_operational_records(
            repo_id=repo_id
        )
        runs = context.workspace.operations.query_runs(repo_id=repo_id)
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "repo_id": repo_id,
                "run_count": len(runs),
                "record_count": len(records),
                "runs": [
                    {
                        "run_id": r.run_id,
                        "workflow": r.workflow.value,
                        "status": r.status.value,
                        "start_ts": r.start_ts,
                    }
                    for r in runs
                ],
                "records": [r.model_dump(mode="json") for r in records],
            },
        )


# ── code-intelligence://governance/{repo}/policy ────────────────────────────


class GovernancePolicyResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://governance/{repo}/policy",
        name="governance-policy",
        description="Permission profiles and tool policy for the given repository.",
        schema_family="governance-policy",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "governance"
            and len(parsed.segments) == 2
            and parsed.segments[1] == "policy"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo_id = parsed.segments[0]
        loader = PermissionProfileLoader()
        profiles = {
            name: {
                "name": p.name,
                "allowed_categories": p.allowed_categories,
                "network_allowed": p.network_allowed,
                "require_approval_for": p.require_approval_for,
                "path_allowlist": p.path_allowlist,
            }
            for name in loader.list_profiles()
            for p in [loader.load(name)]
        }
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "repo_id": repo_id,
                "policy_id": "phase0-default",
                "network_deny_by_default": True,
                "permission_profiles": profiles,
            },
        )


# ── code-intelligence://governance/{repo}/manifest-state ────────────────────


class GovernanceManifestStateResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://governance/{repo}/manifest-state",
        name="governance-manifest-state",
        description=(
            "Current manifest hash state for AGENTS.md, CI workflows, "
            "and harness artefacts for the given repository."
        ),
        schema_family="governance-manifest-state",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "governance"
            and len(parsed.segments) == 2
            and parsed.segments[1] == "manifest-state"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        import hashlib
        from pathlib import Path

        repo_id = parsed.segments[0]

        try:
            repo = context.workspace.repositories.get_repo(repo_id)
            root = Path(repo.root_path)
        except Exception:
            root = Path(repo_id)

        manifests: list[dict[str, object]] = []
        for candidate in [
            "AGENTS.md",
            "CLAUDE.md",
            ".github/workflows/verify.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/governance.yml",
            ".agent/harness-stage.json",
        ]:
            path = root / candidate
            if path.exists():
                content = path.read_bytes()
                manifests.append(
                    {
                        "path": candidate,
                        "sha256": hashlib.sha256(content).hexdigest()[:16],
                        "size_bytes": len(content),
                        "present": True,
                    }
                )
            else:
                manifests.append({"path": candidate, "present": False})

        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "repo_id": repo_id,
                "manifests": manifests,
                "manifest_count": len([m for m in manifests if m.get("present")]),
            },
        )


# ── code-intelligence://readiness/{repo} ────────────────────────────────────


class ReadinessResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://readiness/{repo}",
        name="readiness",
        description="Latest AI-readiness report for the given repository.",
        schema_family="readiness",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "readiness" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo_id = parsed.segments[0]
        reports = context.workspace.operations.query_readiness_reports(repo_id)
        if not reports:
            return _resource_result(
                uri,
                {
                    "schema_version": SCHEMA_VERSION,
                    "repo_id": repo_id,
                    "report": None,
                    "message": "no readiness report found; run compute_readiness_score",
                },
            )
        latest = reports[-1]
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "repo_id": repo_id,
                "report": latest.model_dump(mode="json"),
            },
        )


# ── code-intelligence://incidents/{incident_id} ──────────────────────────────


class IncidentResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://incidents/{incident_id}",
        name="incident",
        description="Incident record for the given incident_id.",
        schema_family="incident",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "incidents" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        incident_id = parsed.segments[0]
        try:
            incident = context.workspace.operations.get_incident(incident_id)
        except RunNotFoundError as exc:
            raise ResourceNotFound(str(exc)) from exc
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "incident": incident.model_dump(mode="json"),
            },
        )


__all__ = [
    "GovernanceManifestStateResource",
    "GovernancePolicyResource",
    "IncidentResource",
    "OperationsLedgerResource",
    "ReadinessResource",
    "RunHarnessConditionResource",
    "RunRecordResource",
]
