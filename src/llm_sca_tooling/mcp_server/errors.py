"""Structured MCP server errors."""

from __future__ import annotations


class McpServerError(Exception):
    code = "mcp_server_error"

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class ServerStartupError(McpServerError):
    code = "server_startup_error"


class ResourceNotFound(McpServerError):
    code = "resource_not_found"


class ResourceInvalidUri(McpServerError):
    code = "resource_invalid_uri"


class ResourceTooLarge(McpServerError):
    code = "resource_too_large"


class ResourceUnavailable(McpServerError):
    code = "resource_unavailable"


class ToolNotFound(McpServerError):
    code = "tool_not_found"


class ToolInvalidArguments(McpServerError):
    code = "tool_invalid_arguments"


class ToolPermissionDenied(McpServerError):
    code = "tool_permission_denied"


class ToolUnavailable(McpServerError):
    code = "tool_unavailable"


class TaskNotFound(McpServerError):
    code = "task_not_found"


class TaskAccessDenied(McpServerError):
    code = "task_access_denied"


class TaskExpired(McpServerError):
    code = "task_expired"
