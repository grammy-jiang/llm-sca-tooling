"""Structured MCP server errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "McpServerError",
    "ResourceInvalidUri",
    "ResourceNotFound",
    "ResourceTooLarge",
    "ToolInvalidArguments",
    "ToolNotFound",
    "ToolPermissionDenied",
    "ToolUnavailable",
    "TaskNotFound",
]


@dataclass
class McpServerError(Exception):
    """Base class for typed MCP errors."""

    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details or {},
        }


class ResourceInvalidUriError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ResourceInvalidUri", message, details)


class ResourceNotFoundError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ResourceNotFound", message, details)


class ResourceTooLargeError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ResourceTooLarge", message, details)


class ToolNotFoundError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ToolNotFound", message, details)


class ToolInvalidArgumentsError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ToolInvalidArguments", message, details)


class ToolPermissionDeniedError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ToolPermissionDenied", message, details)


class ToolUnavailableError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ToolUnavailable", message, details)


class TaskNotFoundError(McpServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("TaskNotFound", message, details)


ResourceInvalidUri = ResourceInvalidUriError
ResourceNotFound = ResourceNotFoundError
ResourceTooLarge = ResourceTooLargeError
ToolNotFound = ToolNotFoundError
ToolInvalidArguments = ToolInvalidArgumentsError
ToolPermissionDenied = ToolPermissionDeniedError
ToolUnavailable = ToolUnavailableError
TaskNotFound = TaskNotFoundError
