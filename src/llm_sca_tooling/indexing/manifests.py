"""Graph manifest and chunk generation."""

from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.indexing.hashing import hash_file, hash_text
from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class GraphManifestGenerator:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def generate(self, repo_id: str, snapshot_id: str, run_id: str, *, chunk_size: int = 1000) -> tuple[str, list[ArtifactRef]]:
        root = self.workspace.storage_root / "artifacts" / "graph"
        root.mkdir(parents=True, exist_ok=True)
        nodes = [row["payload_json"] for row in self.workspace.conn.execute("SELECT payload_json FROM graph_nodes WHERE repo_id=? AND snapshot_id=? ORDER BY node_type, node_id", (repo_id, snapshot_id))]
        edges = [row["payload_json"] for row in self.workspace.conn.execute("SELECT payload_json FROM graph_edges WHERE repo_id=? AND snapshot_id=? ORDER BY edge_type, edge_id", (repo_id, snapshot_id))]
        artifacts: list[ArtifactRef] = []
        for kind, payloads in (("nodes", nodes), ("edges", edges)):
            for index in range(0, len(payloads), chunk_size):
                chunk_payload = {"schema_version": "0.1.0", "kind": kind, "items": [json.loads(item) for item in payloads[index : index + chunk_size]]}
                path = root / f"{repo_id.replace(':', '_')}_{snapshot_id.replace(':', '_')}_{kind}_{index // chunk_size}.json"
                path.write_text(json.dumps(chunk_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                ref = ArtifactRef(
                    artifact_id=f"art:graph:{hash_text(str(path))}",
                    kind=ArtifactKind.GRAPH_CHUNK,
                    uri=str(path),
                    sha256=hash_file(path),
                    size_bytes=path.stat().st_size,
                    media_type="application/json",
                    redaction_status=RedactionStatus.REDACTED,
                    created_ts=_now_ts(),
                )
                self.workspace.artifacts.record_artifact(ref, repo_id=repo_id, run_id=run_id, payload_path=path)
                artifacts.append(ref)
        manifest_id = f"graph:{repo_id}:{snapshot_id}"
        manifest = {
            "graph_id": manifest_id,
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "schema_version": "0.1.0",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "chunk_artifact_ids": [artifact.artifact_id for artifact in artifacts],
            "generated_ts": _now_ts(),
            "indexing_run_id": run_id,
        }
        self.workspace.conn.execute(
            """
            INSERT INTO graph_manifests(graph_id, repo_id, snapshot_id, node_count, edge_count, chunk_artifact_ids_json, schema_version, generated_ts, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(graph_id) DO UPDATE SET node_count=excluded.node_count, edge_count=excluded.edge_count, chunk_artifact_ids_json=excluded.chunk_artifact_ids_json, payload_json=excluded.payload_json
            """,
            (
                manifest_id,
                repo_id,
                snapshot_id,
                len(nodes),
                len(edges),
                json.dumps([artifact.artifact_id for artifact in artifacts]),
                "0.1.0",
                manifest["generated_ts"],
                json.dumps(manifest, sort_keys=True),
            ),
        )
        self.workspace.conn.commit()
        return manifest_id, artifacts
