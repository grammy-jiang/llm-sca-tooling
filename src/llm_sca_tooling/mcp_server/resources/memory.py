"""Memory aggregate MCP resource."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.memory.models import ReviewState
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.storage.workspace import _now_ts


class MemoryTrajectoriesResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://memory/{repo}/trajectories",
        name="memory-trajectories",
        description="Aggregate governed memory metadata for a repository.",
        schema_family="memory",
        size_class="small",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "memory"
            and len(parsed.segments) == 2
            and parsed.segments[1] == "trajectories"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo_id = parsed.segments[0]
        store = MemoryStore(context.workspace.conn)
        policy = store.get_policy()
        trajectories = store.list_trajectories(repo_id)
        project = store.list_project_memory(repo_id)
        payload: JsonObject = {
            "repo_id": repo_id,
            "trajectory_count": len(trajectories),
            "trajectory_count_by_outcome": _counts(
                record.outcome.value for record in trajectories
            ),
            "project_memory_record_count": len(project),
            "last_compaction_ts": store.last_compaction_ts(repo_id),
            "utility_distribution": _counts(
                record.utility.value for record in trajectories
            ),
            "outcome_diversity_summary": sorted(
                {record.outcome.value for record in trajectories}
            ),
            "issue_class_coverage_summary": sorted(
                {record.issue_class for record in trajectories}
            ),
            "memory_policy_status": (
                "enabled" if policy.repo_enabled(repo_id) else "disabled"
            ),
            "last_opt_in_ts": policy.opt_in_ts,
            "ship_gate_status": {"gate_passed": False, "memory_hint_weight": 0.0},
            "unreviewed_record_count": len(
                [
                    record
                    for record in trajectories
                    if record.review_state is ReviewState.UNREVIEWED
                ]
            )
            + len(
                [
                    record
                    for record in project
                    if record.review_state is ReviewState.UNREVIEWED
                ]
            ),
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
            updated_ts=store.last_compaction_ts(repo_id) or _now_ts(),
        )


def _counts(values: Iterable[object]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[str(value)] = result.get(str(value), 0) + 1
    return result


def _etag(payload: JsonObject) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]
