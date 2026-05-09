"""First-class git blame-chain MCP tool."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import ToolDescriptor, ToolHandler, ToolResult
from llm_sca_tooling.qa.blame import BlameLookup
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass
from llm_sca_tooling.storage.errors import RepositoryNotFoundError


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


class GitBlameChainTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="git_blame_chain",
        description="Return cached blame-chain evidence for a file with optional line filtering.",
        input_schema=_schema({"repo": {"type": "string"}, "file": {"type": "string"}, "line": {"type": "integer"}, "line_range": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}, "follow_renames": {"type": "boolean"}, "depth": {"type": "integer"}, "snapshot": {"type": "string"}}, ["repo", "file"]),
        output_schema={"type": "object"},
        read_only=True,
        permission=ToolPermissionDescriptor(required_mode=PermissionMode.SEARCH, path_scope="registered_repo", network_requirement="none", side_effect_class=SideEffectClass.NONE, writes_to_store=False, writes_to_repo=False, runs_subprocesses=False),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo_arg = args.get("repo")
        file_arg = args.get("file")
        if not isinstance(repo_arg, str) or not isinstance(file_arg, str):
            raise ToolInvalidArguments("repo and file are required")
        try:
            repo = context.workspace.repositories.get_repo(repo_arg)
        except RepositoryNotFoundError as exc:
            raise ToolInvalidArguments(str(exc)) from exc
        line_range_arg = args.get("line_range")
        line_range = tuple(int(item) for item in line_range_arg) if isinstance(line_range_arg, list) and len(line_range_arg) == 2 else None
        result = BlameLookup(context.workspace).lookup(repo.repo_id, file_arg, line=int(args["line"]) if args.get("line") is not None else None, line_range=line_range, follow_renames=bool(args.get("follow_renames", True)), depth=int(args.get("depth") or 3))
        return ToolResult(tool_name=self.descriptor.name, status="completed", payload=to_jsonable(result))
