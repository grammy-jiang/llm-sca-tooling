"""Core Phase 4 MCP resource handlers."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

import orjson
from sqlalchemy import text

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.errors import ResourceInvalidUri, ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import (
    parse_resource_uri,
    validate_relative_path,
)
from llm_sca_tooling.plugins.registry import build_default_registry
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.qa.blame import BlameResource
from llm_sca_tooling.sarif.resource import sarif_run_resource, sarif_run_summaries
from llm_sca_tooling.sarif.store import SarifRunStore
from llm_sca_tooling.schemas.graph import GraphDocument
from llm_sca_tooling.schemas.run_records import RunRecord
from llm_sca_tooling.storage.graph_queries import GraphSlice

__all__ = ["CoreResourceHandlers", "register_core_resources"]


def _etag(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def _slice_payload(graph_slice: GraphSlice) -> dict[str, Any]:
    return {
        "repo_id": graph_slice.repo_id,
        "requested_snapshot_id": graph_slice.requested_snapshot_id,
        "snapshot_ids": graph_slice.snapshot_ids,
        "snapshot_consistency": graph_slice.snapshot_consistency,
        "nodes": [n.model_dump(mode="json") for n in graph_slice.nodes],
        "edges": [e.model_dump(mode="json") for e in graph_slice.edges],
        "diagnostics": graph_slice.diagnostics,
        "truncated": graph_slice.truncated,
        "limit": graph_slice.limit,
        "provenance_summary": graph_slice.provenance_summary,
    }


class CoreResourceHandlers:
    def __init__(self, context: McpServerContext) -> None:
        self._context = context
        self._eval_store = EvalStore(
            self._context.config.workspace_path / ".llm-sca" / "eval.sqlite"
        )

    async def repos(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if parsed.segments != ("repos",):
            raise ResourceInvalidUri("repos resource does not accept extra segments")
        repos = await self._context.workspace.registry.list_repos(active_only=True)
        payload_repos = []
        snapshot_refs: list[dict[str, Any]] = []
        for repo in repos:
            latest = await self._context.workspace.snapshots.get_latest_snapshot(
                repo.repo_id
            )
            redacted = repo.redacted()
            redacted.update(
                {
                    "current_branch": repo.current_branch,
                    "latest_snapshot_id": latest.snapshot_id if latest else None,
                    "git_sha": latest.git_sha if latest else None,
                    "worktree_snapshot_id": (
                        latest.worktree_snapshot_id if latest else None
                    ),
                    "dirty": latest.dirty if latest else False,
                    "last_indexed_ts": latest.captured_ts if latest else None,
                    "diagnostics_summary": {"count": 0},
                    "capabilities": repo.capabilities,
                }
            )
            payload_repos.append(redacted)
            if latest:
                snapshot_refs.append(
                    {
                        "repo_id": latest.repo_id,
                        "snapshot_id": latest.snapshot_id,
                        "index_status": latest.index_status,
                    }
                )
        payload = {"resource": "repos", "repos": payload_repos}
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            snapshot_refs=snapshot_refs,
            redaction_status="redacted",
            etag=_etag(payload),
        )

    async def graph_schema(self, uri: str) -> ResourceResult:
        parse_resource_uri(uri)
        payload = GraphDocument.model_json_schema()
        return ResourceResult(
            uri=uri,
            media_type="application/schema+json",
            payload={"schema": payload},
            etag=_etag(payload),
        )

    async def run_record_schema(self, uri: str) -> ResourceResult:
        parse_resource_uri(uri)
        payload = RunRecord.model_json_schema()
        return ResourceResult(
            uri=uri,
            media_type="application/schema+json",
            payload={"schema": payload},
            etag=_etag(payload),
        )

    async def graph_manifest(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) != 2:
            raise ResourceInvalidUri("graph resource requires a repo id")
        repo_id = parsed.segments[1]
        repo = await self._context.workspace.registry.get_repo(repo_id)
        latest = await self._context.workspace.snapshots.get_latest_snapshot(repo_id)
        if latest is None:
            raise ResourceNotFound(f"Repository {repo_id!r} is not indexed")
        node_count = await self._context.workspace.queries.count_nodes(repo_id)
        edge_count = await self._context.workspace.queries.count_edges(repo_id)
        node_type_counts, edge_type_counts = await self._type_counts(repo_id)
        artifacts = await self._context.workspace.artifacts.list_artifacts(
            repo_id=repo_id, limit=100
        )
        chunk_refs = [
            a for a in artifacts if a["kind"] in {"graph_manifest", "graph_chunk"}
        ]
        payload = {
            "graph_id": f"graph:{repo_id}:{latest.snapshot_id}",
            "repo_id": repo.repo_id,
            "snapshot_id": latest.snapshot_id,
            "git_sha": latest.git_sha,
            "worktree_snapshot_id": latest.worktree_snapshot_id,
            "node_count": node_count,
            "edge_count": edge_count,
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "chunk_artifact_refs": chunk_refs,
            "diagnostics_summary": {"count": 0},
            "generated_ts": latest.captured_ts,
            "indexing_run_id": latest.source_run_id,
            "schema_version": "0.1.0",
            "index_status": latest.index_status,
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            artifact_refs=chunk_refs,
            snapshot_refs=[latest.__dict__],
            etag=_etag(payload),
        )

    async def graph_slice(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) < 4:
            raise ResourceInvalidUri("graph slice requires repo and file path")
        repo_id = parsed.segments[2]
        files = [validate_relative_path(part) for part in parsed.segments[3].split(",")]
        generator = GraphSliceGenerator(
            self._context.workspace.queries,
            IndexingConfig(
                graph_slice_limit=self._context.config.max_graph_slice_nodes
            ),
        )
        slices = [await generator.slice_by_file(repo_id, file) for file in files]
        payload = _slice_payload(slices[0])
        if len(slices) > 1:
            payload["nodes"] = [
                node for item in slices for node in _slice_payload(item)["nodes"]
            ]
            payload["edges"] = [
                edge for item in slices for edge in _slice_payload(item)["edges"]
            ]
            payload["snapshot_ids"] = sorted(
                {sid for item in slices for sid in item.snapshot_ids}
            )
            payload["snapshot_consistency"] = (
                "mixed" if len(payload["snapshot_ids"]) > 1 else "clean"
            )
        payload["requested_files"] = files
        diagnostics = [diagnostic for item in slices for diagnostic in item.diagnostics]
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            snapshot_refs=[{"snapshot_id": sid} for sid in payload["snapshot_ids"]],
            diagnostics=diagnostics,
            etag=_etag(payload),
        )

    async def summary(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) < 3:
            raise ResourceInvalidUri("summary resource requires repo and symbol path")
        repo_id = parsed.segments[1]
        symbol_path = parsed.segments[2]
        await self._context.workspace.registry.get_repo(repo_id)
        payload = {
            "repo_id": repo_id,
            "symbol_path": symbol_path,
            "status": "cache_miss",
            "summary": None,
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            diagnostics=[
                {"code": "SUMMARY_CACHE_MISS", "message": "No current summary"}
            ],
            etag=_etag(payload),
        )

    async def blame(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) < 3:
            raise ResourceInvalidUri("blame resource requires repo and file path")
        repo_id = parsed.segments[1]
        file_path = validate_relative_path(parsed.segments[2])
        repo = await self._context.workspace.registry.get_repo(repo_id)
        artifacts = await self._context.workspace.artifacts.list_artifacts(
            repo_id=repo_id, kind="blame", limit=100
        )
        matching = [a for a in artifacts if file_path in a["uri"]]
        blame = BlameResource.from_git(repo.root_path, repo_id, file_path)
        payload = {
            "repo_id": repo_id,
            "file_path": file_path,
            "status": "available" if blame.entries or matching else "cache_miss",
            "entries": [entry.model_dump(mode="json") for entry in blame.entries],
            "artifact_refs": matching,
        }
        diagnostics = [{"message": item} for item in blame.diagnostics]
        if not matching:
            diagnostics.append(
                {"code": "BLAME_CACHE_MISS", "message": "No blame artifact found"}
            )
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            artifact_refs=matching,
            diagnostics=diagnostics,
            etag=_etag(payload),
        )

    async def build_evidence(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) != 2:
            raise ResourceInvalidUri("build-evidence resource requires a repo id")
        repo_id = parsed.segments[1]
        latest = await self._context.workspace.snapshots.get_latest_snapshot(repo_id)
        build_nodes = await self._context.workspace.queries.fetch_nodes_by_type(
            repo_id, "build_target"
        )
        ci_nodes = await self._context.workspace.queries.fetch_nodes_by_type(
            repo_id, "ci_job"
        )
        payload = {
            "repo_id": repo_id,
            "snapshot_id": latest.snapshot_id if latest else None,
            "package_manager_files": [n.file_path for n in build_nodes if n.file_path],
            "ci_jobs": [n.file_path for n in ci_nodes if n.file_path],
            "build_targets": [n.node_id for n in build_nodes],
            "evidence_node_ids": [n.node_id for n in [*build_nodes, *ci_nodes]],
            "has_evidence": bool(build_nodes or ci_nodes),
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            snapshot_refs=([latest.__dict__] if latest else []),
            etag=_etag(payload),
        )

    async def sarif(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) not in {2, 3}:
            raise ResourceInvalidUri("sarif resource requires repo and optional run id")
        repo_id = parsed.segments[1]
        await self._context.workspace.registry.get_repo(repo_id)
        store = SarifRunStore(self._context.workspace)
        if len(parsed.segments) == 2:
            payload = {
                "repo_id": repo_id,
                "runs": await sarif_run_summaries(store, repo_id),
            }
        else:
            run_id = parsed.segments[2]
            try:
                payload = await sarif_run_resource(store, repo_id, run_id)
            except KeyError as exc:
                raise ResourceNotFound(f"SARIF run {run_id!r} not found") from exc
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def interfaces(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if not parsed.segments or parsed.segments[0] != "interfaces":
            raise ResourceInvalidUri("interfaces resource expected")
        store = InterfaceRecordStore(self._context.workspace)
        registry = build_default_registry()
        if len(parsed.segments) == 1:
            records = await store.list_records()
            counts = Counter(record.plugin_id for record in records)
            plugins = []
            for capability in registry.capability_report():
                plugin = registry.get(capability.plugin_id)
                available = (
                    (await plugin.check_availability()).available
                    if plugin is not None
                    else False
                )
                plugins.append(
                    {
                        **capability.model_dump(mode="json"),
                        "available": available,
                        "interface_count": counts.get(capability.plugin_id, 0),
                    }
                )
            payload = {
                "plugins": plugins,
                "total_interface_records": len(records),
                "last_indexed_ts": None,
                "schema_version": "0.1.0",
            }
        elif len(parsed.segments) == 2:
            plugin_id = parsed.segments[1]
            if registry.get(plugin_id) is None:
                raise ResourceNotFound(f"Interface plugin {plugin_id!r} not found")
            records = await store.list_records(plugin_id)
            payload = {
                "plugin_id": plugin_id,
                "interfaces": [
                    {
                        "interface_id": record.interface_id,
                        "interface_name": record.interface_name,
                        "kind": record.kind.value,
                        "repo_ids": record.source_repos,
                    }
                    for record in records
                ],
            }
        elif len(parsed.segments) == 3:
            plugin_id = parsed.segments[1]
            interface_name = parsed.segments[2]
            record = await store.get_record(plugin_id, interface_name)
            if record is None:
                raise ResourceNotFound(
                    f"Interface {plugin_id!r}/{interface_name!r} not found"
                )
            payload = record.model_dump(mode="json")
        else:
            raise ResourceInvalidUri("too many interface resource segments")
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def eval_run(self, uri: str) -> ResourceResult:
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) != 2 or parsed.segments[0] != "eval":
            raise ResourceInvalidUri("eval resource requires a run id")
        payload = self._eval_store.resource_payload(parsed.segments[1])
        if payload.get("status") == "not_found":
            raise ResourceNotFound(f"Eval run {parsed.segments[1]!r} not found")
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def memory_trajectories(self, uri: str) -> ResourceResult:
        """Retained agent trajectories keyed by issue class, FL class, outcome."""
        parsed = parse_resource_uri(uri)
        if (
            len(parsed.segments) != 3
            or parsed.segments[0] != "memory"
            or parsed.segments[2] != "trajectories"
        ):
            raise ResourceInvalidUri(
                "memory resource requires memory/{repo}/trajectories"
            )
        repo_id = parsed.segments[1]
        trajectories = self._context.memory.all_trajectories(repo_id=repo_id)
        payload = {
            "repo_id": repo_id,
            "trajectory_count": len(trajectories),
            "trajectories": [
                {
                    "trajectory_id": t.trajectory_id,
                    "issue_class": t.issue_class,
                    "fl_decisions": t.fl_decisions,
                    "patch_class": t.patch_class,
                    "outcome": t.outcome,
                    "utility": t.utility,
                    "relabelled": t.relabelled,
                    "review_state": t.review_state,
                    "created_ts": t.created_ts,
                }
                for t in trajectories
            ],
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def run_record(self, uri: str) -> ResourceResult:
        """Append-only workflow run record."""
        from llm_sca_tooling.storage.errors import RunNotFoundError  # noqa: PLC0415

        parsed = parse_resource_uri(uri)
        if len(parsed.segments) < 2 or parsed.segments[0] != "runs":
            raise ResourceInvalidUri("runs resource requires runs/{run_id}")
        run_id = parsed.segments[1]
        is_harness_condition = (
            len(parsed.segments) == 3 and parsed.segments[2] == "harness-condition"
        )
        try:
            run = await self._context.workspace.operations.get_run(
                run_id, include_events=not is_harness_condition
            )
        except RunNotFoundError as exc:
            raise ResourceNotFound(f"Run {run_id!r} not found") from exc

        if is_harness_condition:
            if not run.harness_condition_id:
                raise ResourceNotFound(
                    f"Run {run_id!r} has no harness condition recorded"
                )
            hc = await self._context.workspace.operations.get_harness_condition(
                run.harness_condition_id
            )
            if hc is None:
                raise ResourceNotFound(
                    f"Harness condition {run.harness_condition_id!r} not found"
                )
            payload = hc
        else:
            payload = {
                "run_id": run.run_id,
                "workflow": run.workflow,
                "status": run.status,
                "start_ts": run.start_ts,
                "end_ts": run.end_ts,
                "run_event_count": run.run_event_count,
                "harness_condition_id": run.harness_condition_id,
                "final_verdict_id": run.final_verdict_id,
                "events": run.events,
            }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def operations_ledger(self, uri: str) -> ResourceResult:
        """Chronological operational ledger across runs for a repository."""
        parsed = parse_resource_uri(uri)
        if (
            len(parsed.segments) != 3
            or parsed.segments[0] != "operations"
            or parsed.segments[2] != "ledger"
        ):
            raise ResourceInvalidUri(
                "operations resource requires operations/{repo}/ledger"
            )
        repo_id = parsed.segments[1]
        records = await self._context.workspace.operations.query_ledger(repo_id)
        incidents = await self._context.workspace.operations.query_incidents(
            repo_id=repo_id, limit=50
        )
        runs = await self._context.workspace.operations.list_runs(
            repo_id=repo_id, limit=50
        )
        payload = {
            "repo_id": repo_id,
            "record_count": len(records),
            "records": records,
            "recent_incidents": incidents,
            "recent_runs": [
                {
                    "run_id": r.run_id,
                    "workflow": r.workflow,
                    "status": r.status,
                    "start_ts": r.start_ts,
                    "end_ts": r.end_ts,
                }
                for r in runs
            ],
        }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def governance_policy(self, uri: str) -> ResourceResult:
        """Effective permission/tool/path/data policy for a repository."""
        parsed = parse_resource_uri(uri)
        if (
            len(parsed.segments) < 3
            or parsed.segments[0] != "governance"
            or parsed.segments[2] not in ("policy", "manifest-state")
        ):
            raise ResourceInvalidUri(
                "governance resource requires governance/{repo}/policy "
                "or governance/{repo}/manifest-state"
            )
        repo_id = parsed.segments[1]
        subresource = parsed.segments[2]

        try:
            repo = await self._context.workspace.registry.get_repo(repo_id)
        except Exception as exc:
            raise ResourceNotFound(f"Repository {repo_id!r} not found") from exc

        if subresource == "policy":
            harness_meta = await self._context.workspace.harness.get_harness_metadata(
                repo_id, "policy", active_only=True
            )
            payload: dict[str, Any] = {
                "repo_id": repo_id,
                "policy_source": "workspace_defaults",
                "permission_profile": "read-only",
                "write_allowlist": ["src/", "tests/", "schemas/", "docs/"],
                "excluded_paths": [".git/", ".env", "*.key", "*.pem"],
                "tool_dag_stage": "plan",
                "hard_constraints": ["HC1", "HC2", "HC3", "HC4", "HC5", "HC6"],
                "network_policy": "deny-default",
                "data_policy": {"green": "allowed", "amber": "redact", "red": "deny"},
                "overrides": harness_meta,
            }
        else:
            repo_path = repo.root_path
            agents_md_path = repo_path / "AGENTS.md"
            agents_md_exists = agents_md_path.exists()
            claude_md_exists = (repo_path / "CLAUDE.md").exists()
            copilot_instructions_exists = (
                repo_path / ".github" / "copilot-instructions.md"
            ).exists()
            codex_instructions_exists = (
                repo_path / ".codex" / "INSTRUCTIONS.md"
            ).exists()
            drift_findings: list[dict[str, Any]] = []
            if not agents_md_exists:
                drift_findings.append({"artefact": "AGENTS.md", "state": "missing"})
            harness_meta = await self._context.workspace.harness.get_harness_metadata(
                repo_id, "drift", active_only=True
            )
            payload = {
                "repo_id": repo_id,
                "agents_md_present": agents_md_exists,
                "claude_md_present": claude_md_exists,
                "copilot_instructions_present": copilot_instructions_exists,
                "codex_instructions_present": codex_instructions_exists,
                "drift_findings": drift_findings
                + [m for m in harness_meta if isinstance(m, dict)],
                "hard_constraints_enforced": ["HC1", "HC2", "HC3", "HC4", "HC5", "HC6"],
                "overlays_relax_policy": False,
                "harness_stage": "S2",
            }
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def readiness_score(self, uri: str) -> ResourceResult:
        """Repository AI-readiness and tool-readiness score."""
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) != 2 or parsed.segments[0] != "readiness":
            raise ResourceInvalidUri("readiness resource requires readiness/{repo}")
        repo_id = parsed.segments[1]
        latest = await self._context.workspace.operations.get_latest_readiness_report(
            repo_id
        )
        if latest is None:
            payload: dict[str, Any] = {
                "repo_id": repo_id,
                "status": "no_report",
                "message": "No readiness report recorded for this repository. "
                "Run classify_harness_drift or the local-agent-harness CLI.",
            }
        else:
            payload = latest
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )

    async def incident_record(self, uri: str) -> ResourceResult:
        """Incident report for repeated-loop, out-of-scope write, or other failures."""
        parsed = parse_resource_uri(uri)
        if len(parsed.segments) != 2 or parsed.segments[0] != "incidents":
            raise ResourceInvalidUri(
                "incidents resource requires incidents/{incident_id}"
            )
        incident_id = parsed.segments[1]
        incident = await self._context.workspace.operations.get_incident(incident_id)
        if incident is None:
            raise ResourceNotFound(f"Incident {incident_id!r} not found")
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=incident,
            etag=_etag(incident),
        )

    async def _type_counts(self, repo_id: str) -> tuple[dict[str, int], dict[str, int]]:
        async with self._context.workspace._session_factory() as session:
            node_rows = await session.execute(
                text(
                    "SELECT node_type, COUNT(*) FROM graph_nodes "
                    "WHERE repo_id = :repo_id GROUP BY node_type"
                ),
                {"repo_id": repo_id},
            )
            edge_rows = await session.execute(
                text(
                    "SELECT edge_type, COUNT(*) FROM graph_edges "
                    "WHERE repo_id = :repo_id GROUP BY edge_type"
                ),
                {"repo_id": repo_id},
            )
        node_counts = Counter({str(k): int(v) for k, v in node_rows.all()})
        edge_counts = Counter({str(k): int(v) for k, v in edge_rows.all()})
        return dict(node_counts), dict(edge_counts)

    # ── Phase 14 impl-check artifact resources ────────────────────────────────

    async def _impl_check_artifact(self, uri: str) -> ResourceResult:
        """Serve an implementation-check artifact from the in-process store.

        Handles the four URI schemes emitted by run_implementation_check:
          matrix://   – clause-verdict matrix
          spec://     – ingested spec document
          intent-graph:// – intent graph nodes and edges
          trace://    – session trace manifest
        """
        payload = self._context.impl_check_store.get(uri)
        if payload is None:
            raise ResourceNotFound(
                f"No impl-check artifact found for {uri!r}. "
                "Run run_implementation_check first and ensure the run_id matches."
            )
        return ResourceResult(
            uri=uri,
            media_type="application/json",
            payload=payload,
            etag=_etag(payload),
        )


def register_core_resources(
    registry: ResourceRegistry, context: McpServerContext
) -> CoreResourceHandlers:
    handlers = CoreResourceHandlers(context)
    entries = [
        (
            ResourceDescriptor(
                uri_template="code-intelligence://repos",
                name="repos",
                description="Registered repositories and current index status.",
            ),
            handlers.repos,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://schema/graph.schema.json",
                name="graph-schema",
                description="Graph JSON Schema.",
                media_type="application/schema+json",
                subscribable=False,
                freshness="static",
            ),
            handlers.graph_schema,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://schema/run-record.schema.json",
                name="run-record-schema",
                description="Run-record JSON Schema.",
                media_type="application/schema+json",
                subscribable=False,
                freshness="static",
            ),
            handlers.run_record_schema,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://graph/{repo}",
                name="graph",
                description="Graph manifest and chunk references.",
                size_class="large",
            ),
            handlers.graph_manifest,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://graph/slice/{repo}/{files}",
                name="graph-slice",
                description="Bounded graph slice for one or more files.",
            ),
            handlers.graph_slice,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://summary/{repo}/{symbol_path}",
                name="summary",
                description="Cached symbol summary.",
            ),
            handlers.summary,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://blame/{repo}/{file_path}",
                name="blame",
                description="Blame-chain evidence for a file.",
                subscribable=True,
            ),
            handlers.blame,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://build-evidence/{repo}",
                name="build-evidence",
                description="Detected build/test/CI evidence.",
            ),
            handlers.build_evidence,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://sarif/{repo}",
                name="sarif-list",
                description="Stored SARIF runs for a repository.",
            ),
            handlers.sarif,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://sarif/{repo}/{run_id}",
                name="sarif-run",
                description="Normalized SARIF run evidence.",
            ),
            handlers.sarif,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://interfaces",
                name="interfaces",
                description="Registered interface plugins and indexed interfaces.",
                subscribable=True,
            ),
            handlers.interfaces,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://interfaces/{plugin_id}",
                name="interfaces-by-plugin",
                description="Indexed interface names for one plugin.",
                subscribable=True,
            ),
            handlers.interfaces,
        ),
        (
            ResourceDescriptor(
                uri_template=(
                    "code-intelligence://interfaces/{plugin_id}/{interface_name}"
                ),
                name="interface-record",
                description="Single indexed interface record.",
                subscribable=True,
            ),
            handlers.interfaces,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://eval/{run_id}",
                name="eval-run",
                description=(
                    "Evaluation run metadata, metrics, freshness, and RDS summary."
                ),
                subscribable=True,
            ),
            handlers.eval_run,
        ),
        # ── Phase 19 operational harness resources ──────────────────────────
        (
            ResourceDescriptor(
                uri_template="code-intelligence://memory/{repo}/trajectories",
                name="memory-trajectories",
                description=(
                    "Retained agent trajectories keyed by issue class, FL class, "
                    "patch class, outcome, and utility score."
                ),
                subscribable=True,
            ),
            handlers.memory_trajectories,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://runs/{run_id}",
                name="run-record",
                description=(
                    "Append-only workflow run record: user intent hash, workflow type, "
                    "stage transitions, tool calls, approvals/denials, evidence IDs, "
                    "budget events, compaction events, gate results, final verdict, "
                    "and reviewer decision."
                ),
                subscribable=True,
            ),
            handlers.run_record,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://runs/{run_id}/harness-condition",
                name="run-harness-condition",
                description=(
                    "Harness-condition sheet for a run: model/backend, server/skill "
                    "versions, exposed tool set, permission profile, sandbox/network "
                    "policy, context policy, verification gates, telemetry/redaction "
                    "policy, and recovery mode."
                ),
                subscribable=True,
            ),
            handlers.run_record,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://operations/{repo}/ledger",
                name="operations-ledger",
                description=(
                    "Chronological operational ledger across runs: anomalies, blocked "
                    "operations, budget overruns, repeated failures, incident links, "
                    "memory promotions, and policy/ruleset changes."
                ),
                subscribable=True,
            ),
            handlers.operations_ledger,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://governance/{repo}/policy",
                name="governance-policy",
                description=(
                    "Effective permission/tool/path/data policy resolved from "
                    "workspace defaults, repo configuration, workflow policy, "
                    "and user-approved overrides."
                ),
            ),
            handlers.governance_policy,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://governance/{repo}/manifest-state",
                name="governance-manifest-state",
                description=(
                    "Parsed instruction/control-plane state, hard constraints, "
                    "runtime overlays, harness stage, drift findings, and "
                    "whether overlays relax the AGENTS.md policy."
                ),
            ),
            handlers.governance_policy,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://readiness/{repo}",
                name="readiness-score",
                description=(
                    "Repository AI-readiness and tool-readiness score across agent "
                    "config, docs/spec coverage, CI/build evidence, code structure, "
                    "security scanning, and available deterministic gates."
                ),
                subscribable=True,
            ),
            handlers.readiness_score,
        ),
        (
            ResourceDescriptor(
                uri_template="code-intelligence://incidents/{incident_id}",
                name="incident-record",
                description=(
                    "Incident report for failures such as repeated-loop, out-of-scope "
                    "write attempt, secret exposure, verification bypass, stale-index "
                    "verdict, or budget exhaustion."
                ),
                subscribable=True,
            ),
            handlers.incident_record,
        ),
        # ── Phase 14 impl-check artifact resource URI schemes ─────────────────
        (
            ResourceDescriptor(
                uri_template="matrix://{run_id}",
                name="impl-check-matrix",
                description=(
                    "Clause-verdict matrix for an implementation-check run: "
                    "per-clause final verdicts, confidence, ECE bucket, and "
                    "overall compliance status."
                ),
                subscribable=False,
                freshness="snapshot-aware",
            ),
            handlers._impl_check_artifact,
        ),
        (
            ResourceDescriptor(
                uri_template="spec://{doc_id}",
                name="impl-check-spec",
                description=(
                    "Ingested specification document used in an implementation-check "
                    "run: source path, content hash, clause count, and provenance."
                ),
                subscribable=False,
                freshness="static",
            ),
            handlers._impl_check_artifact,
        ),
        (
            ResourceDescriptor(
                uri_template="intent-graph://{intent_id}",
                name="impl-check-intent-graph",
                description=(
                    "Intent graph nodes and edges derived from a spec document: "
                    "clause decompositions, satisfies/violates/checks edges."
                ),
                subscribable=False,
                freshness="snapshot-aware",
            ),
            handlers._impl_check_artifact,
        ),
        (
            ResourceDescriptor(
                uri_template="trace://{run_id}",
                name="impl-check-trace",
                description=(
                    "Session trace manifest for an implementation-check run: "
                    "clause count, overall verdict, and harness condition id."
                ),
                subscribable=False,
                freshness="snapshot-aware",
            ),
            handlers._impl_check_artifact,
        ),
    ]
    for descriptor, handler in entries:
        registry.register(descriptor, handler)
    return handlers
