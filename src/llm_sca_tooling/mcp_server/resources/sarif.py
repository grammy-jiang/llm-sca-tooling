"""SARIF MCP resources."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.mcp_server.resources.core import _resource_result
from llm_sca_tooling.sarif.resource import sarif_run_resource_payload
from llm_sca_tooling.storage.errors import RepositoryNotFoundError


class SarifResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://sarif/{repo}/{run_id}",
        name="sarif-run",
        description="Normalized SARIF run evidence and alert summaries.",
        schema_family="sarif-run",
        size_class="bounded",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "sarif" and len(parsed.segments) == 2

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        run = context.workspace.sarif.get_run(parsed.segments[1])
        if run is None:
            raise ResourceNotFound(f"SARIF run not found: {parsed.segments[1]}")
        if run.repo_id != repo.repo_id:
            raise ResourceNotFound(f"SARIF run does not belong to repo: {repo.repo_id}")
        delta = None
        if run.delta_from_run_id:
            delta_id = "sarif-delta:"  # noqa: F841
            rows = context.workspace.conn.execute(
                "SELECT delta_id FROM sarif_deltas WHERE after_run_id=? ORDER BY computed_ts DESC LIMIT 1",
                (run.run_id,),
            ).fetchall()
            delta = (
                context.workspace.sarif.get_delta(rows[0]["delta_id"]) if rows else None
            )
        artifacts = [run.raw_sarif_artifact_ref] if run.raw_sarif_artifact_ref else []
        snapshot = context.workspace.snapshots.get_snapshot(run.snapshot_id).snapshot
        return _resource_result(
            uri,
            sarif_run_resource_payload(run, delta),
            artifacts=artifacts,
            snapshots=[snapshot],
        )


class SarifListResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://sarif/{repo}",
        name="sarif-run-list",
        description="Stored SARIF run IDs for a repository.",
        schema_family="sarif-run-list",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "sarif" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        runs = context.workspace.sarif.list_runs(repo.repo_id)
        payload = {
            "repo_id": repo.repo_id,
            "runs": [
                {
                    "run_id": run.run_id,
                    "analyser_id": run.analyser_id,
                    "ruleset_id": run.ruleset_id,
                    "alert_count": len(run.alerts),
                    "rule_count": len(run.rules),
                    "invocation_start_ts": run.invocation_start_ts,
                }
                for run in runs
            ],
        }
        return _resource_result(uri, payload)


def _repo(context: McpRequestContext, repo_id_or_name: str):
    try:
        return context.workspace.repositories.get_repo(repo_id_or_name)
    except RepositoryNotFoundError as exc:
        raise ResourceNotFound(str(exc)) from exc
