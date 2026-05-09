"""Structured MCP server errors."""

from __future__ import annotations


class McpServerError(Exception):
    code = "mcp_server_error"

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class ServerStartupError(McpServerError):
    code = "server_startup_error"


class ResourceNotFound(McpServerError):  # noqa: N818
    code = "resource_not_found"


class ResourceInvalidUri(McpServerError):  # noqa: N818
    code = "resource_invalid_uri"


class ResourceTooLarge(McpServerError):  # noqa: N818
    code = "resource_too_large"


class ResourceUnavailable(McpServerError):  # noqa: N818
    code = "resource_unavailable"


class ToolNotFound(McpServerError):  # noqa: N818
    code = "tool_not_found"


class ToolInvalidArguments(McpServerError):  # noqa: N818
    code = "tool_invalid_arguments"


class ToolPermissionDenied(McpServerError):  # noqa: N818
    code = "tool_permission_denied"


class ToolUnavailable(McpServerError):  # noqa: N818
    code = "tool_unavailable"


class TaskNotFound(McpServerError):  # noqa: N818
    code = "task_not_found"


class TaskAccessDenied(McpServerError):  # noqa: N818
    code = "task_access_denied"


class TaskExpired(McpServerError):  # noqa: N818
    code = "task_expired"


class ResourceStale(McpServerError):  # noqa: N818
    code = "resource_stale"


class ResourcePermissionDenied(McpServerError):  # noqa: N818
    code = "resource_permission_denied"


class ResourceSchemaError(McpServerError):
    code = "resource_schema_error"


class ToolApprovalRequired(McpServerError):  # noqa: N818
    code = "tool_approval_required"


class ToolExecutionFailed(McpServerError):  # noqa: N818
    code = "tool_execution_failed"


class ToolTaskRequired(McpServerError):  # noqa: N818
    code = "tool_task_required"


class ToolSchemaError(McpServerError):
    code = "tool_schema_error"
