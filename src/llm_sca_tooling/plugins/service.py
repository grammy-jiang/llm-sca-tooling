"""Plugin reload orchestration."""

from __future__ import annotations

from llm_sca_tooling.plugins.base import PluginConfig, repo_files
from llm_sca_tooling.plugins.registry import PluginRegistry
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["reload_plugins"]


async def reload_plugins(
    workspace: WorkspaceStore,
    registry: PluginRegistry,
    *,
    plugin_id: str | None = None,
    repo_ids: list[str] | None = None,
) -> dict[str, object]:
    plugins = [
        plugin
        for plugin in await registry.available_plugins()
        if plugin_id is None or plugin.plugin_id == plugin_id
    ]
    diagnostics: list[str] = []
    if plugin_id and not registry.get(plugin_id):
        diagnostics.append(f"UNKNOWN_PLUGIN:{plugin_id}")
    repos = (
        [await workspace.registry.get_repo(repo_id) for repo_id in repo_ids]
        if repo_ids
        else await workspace.registry.list_repos(active_only=True)
    )
    store = InterfaceRecordStore(workspace)
    records_updated = 0
    nodes_added = 0
    edges_added = 0
    plugins_reloaded: list[str] = []
    for plugin in plugins:
        for repo in repos:
            snapshot = await workspace.snapshots.get_latest_snapshot(repo.repo_id)
            if snapshot is None:
                diagnostics.append(f"REPO_NOT_INDEXED:{repo.repo_id}")
                continue
            detected = await plugin.detect(repo, snapshot, repo_files(repo.root_path))
            indexed = await plugin.index(repo, snapshot, detected, PluginConfig())
            linked = await plugin.link(
                repo, snapshot, indexed, workspace, PluginConfig()
            )
            await store.store_records(indexed.interface_records)
            records_updated += len(indexed.interface_records)
            nodes_added += linked.nodes_emitted
            edges_added += linked.edges_emitted
            plugins_reloaded.append(plugin.plugin_id)
            diagnostics.extend(str(item) for item in indexed.diagnostics)
            diagnostics.extend(str(item) for item in linked.diagnostics)
    return {
        "plugins_reloaded": sorted(set(plugins_reloaded)),
        "repos_reloaded": [repo.repo_id for repo in repos],
        "interface_records_updated": records_updated,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "nodes_removed": 0,
        "diagnostics": diagnostics,
        "notifications_emitted": ["code-intelligence://interfaces"],
        "run_event_ids": [],
    }
