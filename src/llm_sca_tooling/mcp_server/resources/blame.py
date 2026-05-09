"""First-class cached blame resource."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.resource_registry import ResourceDescriptor, ResourceHandler, ResourceResult
from llm_sca_tooling.mcp_server.resource_uris import ParsedResourceUri
from llm_sca_tooling.mcp_server.resources.core import _resource_result
from llm_sca_tooling.qa.blame import BlameLookup
from llm_sca_tooling.storage.errors import RepositoryNotFoundError


class BlameResource(ResourceHandler):
    descriptor = ResourceDescriptor(
        uri_template="code-intelligence://blame/{repo}/{file_path}",
        name="blame-chain",
        description="Cached git blame-chain evidence with diagnostics for untracked or binary files.",
        schema_family="blame-chain",
        size_class="artifact-backed",
        freshness="snapshot-aware",
        subscribable=True,
    )

    def matches(self, parsed: ParsedResourceUri) -> bool:
        return parsed.authority == "blame" and len(parsed.segments) >= 2

    def read(self, context: McpRequestContext, uri: str, parsed: ParsedResourceUri) -> ResourceResult:
        try:
            repo = context.workspace.repositories.get_repo(parsed.segments[0])
        except RepositoryNotFoundError as exc:
            raise ResourceNotFound(str(exc)) from exc
        file_path = "/".join(parsed.segments[1:])
        result = BlameLookup(context.workspace).lookup(repo.repo_id, file_path)
        return _resource_result(uri, {"status": "found" if result.entries else "cache_miss", "blame": result.model_dump(mode="json"), "diagnostics": [{"code": code} for code in result.diagnostics]})
