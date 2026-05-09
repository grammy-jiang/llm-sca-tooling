"""Interface plugin MCP resources."""

from __future__ import annotations

from urllib.parse import unquote

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import (
    ResourceDescriptor,
    ResourceHandler,
    ResourceResult,
)
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.mcp_server.resources.core import _resource_result
from llm_sca_tooling.plugins.registry import default_plugin_registry
from llm_sca_tooling.plugins.store import InterfaceIndexStore
from llm_sca_tooling.schemas.base import SCHEMA_VERSION


class InterfacesResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://interfaces",
        name="interfaces",
        description="Registered interface plugins and indexed interface contracts.",
        schema_family="interface-list",
        subscribable=True,
        listable=True,
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "interfaces"

    def read(
        self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri
    ) -> ResourceResult:
        store = InterfaceIndexStore(context.workspace)
        registry = default_plugin_registry()
        if not parsed.segments:
            records = store.list_records()
            plugin_summaries = []
            for plugin in registry.all_plugins():
                plugin_records = [
                    record for record in records if record.plugin_id == plugin.plugin_id
                ]
                availability = plugin.check_availability()
                plugin_summaries.append(
                    {
                        "plugin_id": plugin.plugin_id,
                        "plugin_version": plugin.plugin_version,
                        "interface_kind": plugin.interface_kind.value,
                        "available": availability.available,
                        "interface_count": len(plugin_records),
                        "repos_indexed": sorted(
                            {
                                repo
                                for record in plugin_records
                                for repo in record.source_repos
                            }
                        ),
                        "last_indexed_ts": max(
                            [record.last_indexed_ts or "" for record in plugin_records],
                            default=None,
                        ),
                    }
                )
            return _resource_result(
                uri,
                {
                    "schema_version": SCHEMA_VERSION,
                    "plugins": plugin_summaries,
                    "total_interface_records": len(records),
                    "last_indexed_ts": max(
                        [record.last_indexed_ts or "" for record in records],
                        default=None,
                    ),
                },
            )
        plugin_id = unquote(parsed.segments[0])
        if registry.get(plugin_id) is None:
            raise ResourceNotFound(f"unknown interface plugin: {plugin_id}")
        if len(parsed.segments) == 1:
            records = store.list_records(plugin_id=plugin_id)
            return _resource_result(
                uri,
                {
                    "plugin_id": plugin_id,
                    "interfaces": [
                        {
                            "interface_id": record.interface_id,
                            "interface_name": record.interface_name,
                            "kind": record.kind.value,
                            "repo_ids": record.source_repos,
                            "last_indexed_ts": record.last_indexed_ts,
                        }
                        for record in records
                    ],
                },
            )
        interface_name = unquote("/".join(parsed.segments[1:]))
        record = store.get_record(plugin_id, interface_name)
        if record is None:
            raise ResourceNotFound(f"interface not found: {plugin_id}/{interface_name}")
        return _resource_result(uri, record.model_dump(mode="json"))
