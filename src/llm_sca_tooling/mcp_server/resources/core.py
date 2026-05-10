"""Core index resource handlers."""

from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.indexing.summaries import SummaryCache, SymbolSummaryRecord
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceInvalidUri, ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import (
    ParsedResourceUri,
    decode_repo_relative_path,
)
from llm_sca_tooling.mcp_server.serialization import canonical_json_bytes
from llm_sca_tooling.schemas.base import SCHEMA_VERSION, JsonObject
from llm_sca_tooling.schemas.enums import ArtifactKind, GraphNodeType
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.errors import (
    ArtifactNotFoundError,
    RepositoryNotFoundError,
)
from llm_sca_tooling.storage.workspace import _now_ts


def _etag(payload: object) -> str:
    return hash_text(canonical_json_bytes(payload).decode("utf-8"), length=32)


def _resource_result(
    uri: str,
    payload: JsonObject,
    *,
    media_type: str = "application/json",
    artifacts: list[ArtifactRef] | None = None,
    snapshots=None,
    diagnostics=None,
    updated_ts: str | None = None,
) -> ResourceResult:
    return ResourceResult(
        uri=uri,
        media_type=media_type,
        payload=payload,
        artifact_refs=artifacts or [],
        snapshot_refs=snapshots or [],
        diagnostics=diagnostics or [],
        etag=_etag(payload),
        updated_ts=updated_ts or _now_ts(),
    )


class ReposResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://repos",
        name="repos",
        description="Registered repositories and current index status.",
        schema_family="repository-list",
        freshness="live-registry",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "repos" and not parsed.segments

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repositories = []
        snapshots = []
        for repo in context.workspace.repositories.list_repos(active_only=True):
            payload = repo.public_metadata()
            latest = context.workspace.snapshots.get_latest_snapshot(repo.repo_id)
            if latest:
                payload.update(
                    {
                        "latest_snapshot_id": latest.snapshot_id,
                        "git_sha": latest.snapshot.git_sha,
                        "worktree_snapshot_id": latest.snapshot.worktree_snapshot_id,
                        "dirty": latest.snapshot.dirty,
                        "index_status": latest.snapshot.index_status.value,
                        "last_indexed_ts": latest.snapshot.captured_ts,
                    }
                )
                snapshots.append(latest.snapshot)
            repositories.append(payload)
        return _resource_result(
            uri,
            {
                "schema_version": SCHEMA_VERSION,
                "repositories": repositories,
                "count": len(repositories),
            },
            snapshots=snapshots,
        )


class SchemaResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://schema/{schema_file}",
        name="schemas",
        description="Checked-in Phase 1 JSON Schema exports.",
        media_type="application/schema+json",
        schema_family="json-schema",
        subscribable=False,
        freshness="immutable-file",
    )

    allowed = {"graph.schema.json", "run-record.schema.json"}

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "schema"
            and len(parsed.segments) == 1
            and parsed.segments[0] in self.allowed
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        path = context.config.schema_dir / parsed.segments[0]
        if not path.exists():
            raise ResourceNotFound(f"schema not found: {parsed.segments[0]}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _resource_result(uri, payload, media_type="application/schema+json")


class GraphManifestResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://graph/{repo}",
        name="graph-manifest",
        description="Graph manifest and chunk artifact references for a repository.",
        schema_family="graph-manifest",
        size_class="manifest",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "graph" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        row = context.workspace.conn.execute(
            "SELECT * FROM graph_manifests WHERE repo_id=? ORDER BY generated_ts DESC LIMIT 1",
            (repo.repo_id,),
        ).fetchone()
        if row is None:
            raise ResourceNotFound(f"graph is not indexed for repo: {repo.repo_id}")
        manifest = json.loads(row["payload_json"])
        snapshot = context.workspace.snapshots.get_snapshot(row["snapshot_id"]).snapshot
        node_counts = _counts(
            context, "graph_nodes", "node_type", repo.repo_id, row["snapshot_id"]
        )
        edge_counts = _counts(
            context, "graph_edges", "edge_type", repo.repo_id, row["snapshot_id"]
        )
        artifacts = []
        for artifact_id in json.loads(row["chunk_artifact_ids_json"]):
            try:
                artifacts.append(context.workspace.artifacts.get_artifact(artifact_id))
            except ArtifactNotFoundError:
                pass
        manifest.update(
            {
                "node_type_counts": node_counts,
                "edge_type_counts": edge_counts,
                "index_status": snapshot.index_status.value,
            }
        )
        return _resource_result(
            uri,
            manifest,
            artifacts=artifacts,
            snapshots=[snapshot],
            updated_ts=row["generated_ts"],
        )


class GraphSliceResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://graph/slice/{repo}/{files}",
        name="graph-slice",
        description="Bounded graph slice around one or more repo-relative files.",
        schema_family="graph-slice",
        size_class="bounded",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return (
            parsed.authority == "graph"
            and len(parsed.segments) >= 3
            and parsed.segments[0] == "slice"
        )

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[1])
        file_expr = "/".join(parsed.segments[2:])
        file_paths = [
            decode_repo_relative_path(part) for part in file_expr.split(",") if part
        ]
        if not file_paths:
            raise ResourceInvalidUri("at least one file path is required")
        generator = GraphSliceGenerator(context.workspace)
        nodes = {}
        edges = {}
        snapshot_ids: set[str] = set()
        snapshot_consistency = "unknown"
        for file_path in file_paths:
            graph_slice = generator.by_file(
                repo.repo_id, file_path, limit=context.config.max_graph_slice_nodes
            )
            snapshot_ids.update(graph_slice.snapshot_ids)
            snapshot_consistency = graph_slice.snapshot_consistency.value
            for node in graph_slice.nodes:
                nodes[node.node_id] = node
            for edge in graph_slice.edges:
                edges[edge.edge_id] = edge
        payload = {
            "repo_id": repo.repo_id,
            "requested_files": file_paths,
            "nodes": [node.model_dump(mode="json") for node in nodes.values()],
            "edges": [edge.model_dump(mode="json") for edge in edges.values()],
            "snapshot_ids": sorted(snapshot_ids),
            "snapshot_consistency": snapshot_consistency,
            "truncated": len(nodes) > context.config.max_graph_slice_nodes
            or len(edges) > context.config.max_graph_slice_edges,
            "provenance_summary": {"node_count": len(nodes), "edge_count": len(edges)},
        }
        return _resource_result(uri, payload)


class SummaryResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://summary/{repo}/{symbol_path}",
        name="symbol-summary",
        description="Cached symbol summary records.",
        schema_family="symbol-summary",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "summary" and len(parsed.segments) >= 2

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        symbol_path = "/".join(parsed.segments[1:])
        record = _find_summary(context, repo.repo_id, symbol_path)
        if record is None:
            return _resource_result(
                uri,
                {
                    "status": "cache_miss",
                    "repo_id": repo.repo_id,
                    "symbol_path": symbol_path,
                },
            )
        return _resource_result(
            uri,
            {"status": "current", "summary": record.model_dump(mode="json")},
            snapshots=[],
        )


class BlameResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://blame/{repo}/{file_path}",
        name="blame-chain",
        description="Cached git blame-chain evidence.",
        schema_family="blame-chain",
        size_class="artifact-backed",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "blame" and len(parsed.segments) >= 2

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        file_path = decode_repo_relative_path("/".join(parsed.segments[1:]))
        chain, artifact = _find_blame(context, repo.repo_id, file_path)
        if chain is None:
            return _resource_result(
                uri,
                {
                    "status": "cache_miss",
                    "repo_id": repo.repo_id,
                    "file_path": file_path,
                    "diagnostics": [{"code": "blame_cache_miss"}],
                },
            )
        return _resource_result(
            uri,
            {"status": "found", "blame": chain},
            artifacts=[artifact] if artifact else [],
        )


class BuildEvidenceResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://build-evidence/{repo}",
        name="build-evidence",
        description="Detected package, test, and CI evidence.",
        schema_family="build-evidence",
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "build-evidence" and len(parsed.segments) == 1

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        repo = _repo(context, parsed.segments[0])
        latest = context.workspace.snapshots.get_latest_snapshot(repo.repo_id)
        snapshot_id = latest.snapshot_id if latest else None
        nodes = []
        for node_type in (
            GraphNodeType.BUILD_TARGET,
            GraphNodeType.TEST,
            GraphNodeType.CI_JOB,
        ):
            nodes.extend(
                context.workspace.graph.fetch_nodes_by_type(
                    repo.repo_id, node_type, snapshot_id=snapshot_id
                )
            )
        payload = {
            "repo_id": repo.repo_id,
            "snapshot_id": snapshot_id,
            "status": "found" if nodes else "empty",
            "build_targets": [
                node.model_dump(mode="json")
                for node in nodes
                if node.node_type == GraphNodeType.BUILD_TARGET
            ],
            "tests": [
                node.model_dump(mode="json")
                for node in nodes
                if node.node_type == GraphNodeType.TEST
            ],
            "ci_jobs": [
                node.model_dump(mode="json")
                for node in nodes
                if node.node_type == GraphNodeType.CI_JOB
            ],
            "tests_run": False,
        }
        return _resource_result(
            uri, payload, snapshots=[latest.snapshot] if latest else []
        )


def default_resource_handlers() -> list[ResourceHandler]:
    from llm_sca_tooling.mcp_server.resources.blame import (
        BlameResource as Phase8BlameResource,
    )
    from llm_sca_tooling.mcp_server.resources.eval import EvalResource
    from llm_sca_tooling.mcp_server.resources.interfaces import (
        InterfaceDetailResource,
        InterfacesResource,
    )
    from llm_sca_tooling.mcp_server.resources.memory import MemoryTrajectoriesResource
    from llm_sca_tooling.mcp_server.resources.operational import (
        GovernanceManifestStateResource,
        GovernancePolicyResource,
        IncidentResource,
        OperationsLedgerResource,
        ReadinessResource,
        RunHarnessConditionResource,
        RunRecordResource,
    )
    from llm_sca_tooling.mcp_server.resources.sarif import (
        SarifListResource,
        SarifResource,
    )

    return [
        ReposResource(),
        SchemaResource(),
        GraphSliceResource(),
        GraphManifestResource(),
        SummaryResource(),
        Phase8BlameResource(),
        BuildEvidenceResource(),
        InterfacesResource(),
        InterfaceDetailResource(),
        SarifListResource(),
        SarifResource(),
        EvalResource(),
        MemoryTrajectoriesResource(),
        RunRecordResource(),
        RunHarnessConditionResource(),
        OperationsLedgerResource(),
        GovernancePolicyResource(),
        GovernanceManifestStateResource(),
        ReadinessResource(),
        IncidentResource(),
    ]


def _repo(context: McpRequestContext, repo_id_or_name: str):
    try:
        return context.workspace.repositories.get_repo(repo_id_or_name)
    except RepositoryNotFoundError as exc:
        raise ResourceNotFound(str(exc)) from exc


def _counts(
    context: McpRequestContext, table: str, column: str, repo_id: str, snapshot_id: str
) -> JsonObject:
    return {
        row[column]: row["count"]
        for row in context.workspace.conn.execute(
            f"SELECT {column}, count(*) AS count FROM {table} WHERE repo_id=? AND snapshot_id=? GROUP BY {column}",
            (repo_id, snapshot_id),
        )
    }


def _find_summary(
    context: McpRequestContext, repo_id: str, symbol_path: str
) -> SymbolSummaryRecord | None:
    cache = SummaryCache(context.workspace.storage_root / "summaries")
    for path in cache.root.glob("summary_*.json"):
        record = SymbolSummaryRecord.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if (
            record.repo_id == repo_id
            and record.symbol_path == symbol_path
            and record.invalidated_ts is None
        ):
            return record
    return None


def _find_blame(
    context: McpRequestContext, repo_id: str, file_path: str
) -> tuple[JsonObject | None, ArtifactRef | None]:
    for artifact in context.workspace.artifacts.list_artifacts(
        repo_id=repo_id, kind=ArtifactKind.REPORT.value
    ):
        if not artifact.artifact_id.startswith("art:blame:"):
            continue
        path = Path(artifact.uri)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("repo_id") == repo_id and payload.get("file_path") == file_path:
            return payload, artifact
    return None, None
