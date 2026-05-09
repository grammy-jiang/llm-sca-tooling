"""Index-time runner for interface plugins."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.plugins.base import PluginConfig
from llm_sca_tooling.plugins.registry import PluginRegistry, default_plugin_registry
from llm_sca_tooling.plugins.store import InterfaceIndexStore
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import Severity
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import WorkspaceStore


class PluginRunSummary(StrictBaseModel):
    plugins_run: list[str] = Field(default_factory=list)
    interface_records: int = 0
    nodes_added: int = 0
    edges_added: int = 0
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)


def run_interface_plugins(
    workspace: WorkspaceStore,
    repo_root: Path,
    repo: RepoRef,
    snapshot: SnapshotRef,
    files: list[ScannedFile],
    *,
    run_id: str | None = None,
    registry: PluginRegistry | None = None,
    plugin_ids: list[str] | None = None,
) -> PluginRunSummary:
    registry = registry or default_plugin_registry()
    selected = (
        [registry.require(plugin_id) for plugin_id in plugin_ids]
        if plugin_ids
        else registry.available_plugins()
    )
    config = PluginConfig(repo_root=repo_root, run_id=run_id)
    store = InterfaceIndexStore(workspace)
    summary = PluginRunSummary()
    for plugin in selected:
        availability = plugin.check_availability()
        if not availability.available:
            summary.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:{plugin.plugin_id}:unavailable",
                    severity=Severity.INFO,
                    code="PLUGIN_UNAVAILABLE",
                    message=f"Plugin unavailable: {plugin.plugin_id}",
                    details={"missing_deps": availability.missing_deps},
                )
            )
            continue
        detect_result = plugin.detect(repo, snapshot, files, config)
        index_result = plugin.index(repo, snapshot, detect_result, config)
        link_result = plugin.link(repo, snapshot, index_result, workspace.graph, config)
        store.upsert_records(index_result.interface_records, run_id=run_id)
        summary.plugins_run.append(plugin.plugin_id)
        summary.interface_records += len(index_result.interface_records)
        summary.nodes_added += link_result.nodes_emitted
        summary.edges_added += link_result.edges_emitted
        summary.diagnostics.extend(
            [
                *detect_result.diagnostics,
                *index_result.diagnostics,
                *link_result.diagnostics,
            ]
        )
    return summary
