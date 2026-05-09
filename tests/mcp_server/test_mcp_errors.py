"""Tests for MCP server error classes."""

from __future__ import annotations

import pytest

from llm_sca_tooling.mcp_server.errors import (
    McpServerError,
    ResourceInvalidUri,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceSchemaError,
    ResourceStale,
    ResourceTooLarge,
    ResourceUnavailable,
    ServerStartupError,
    TaskAccessDenied,
    TaskExpired,
    TaskNotFound,
    ToolApprovalRequired,
    ToolExecutionFailed,
    ToolInvalidArguments,
    ToolNotFound,
    ToolPermissionDenied,
    ToolSchemaError,
    ToolTaskRequired,
    ToolUnavailable,
)

_ALL_ERROR_CLASSES = [
    McpServerError,
    ServerStartupError,
    ResourceNotFound,
    ResourceInvalidUri,
    ResourceTooLarge,
    ResourceUnavailable,
    ResourceStale,
    ResourcePermissionDenied,
    ResourceSchemaError,
    ToolNotFound,
    ToolInvalidArguments,
    ToolPermissionDenied,
    ToolUnavailable,
    ToolApprovalRequired,
    ToolExecutionFailed,
    ToolTaskRequired,
    ToolSchemaError,
    TaskNotFound,
    TaskAccessDenied,
    TaskExpired,
]

_NEW_CLASSES = [
    ResourceStale,
    ResourcePermissionDenied,
    ResourceSchemaError,
    ToolApprovalRequired,
    ToolExecutionFailed,
    ToolTaskRequired,
    ToolSchemaError,
]


@pytest.mark.parametrize("cls", _ALL_ERROR_CLASSES)
def test_error_inherits_from_mcp_server_error(cls) -> None:
    assert issubclass(cls, McpServerError)


@pytest.mark.parametrize("cls", _ALL_ERROR_CLASSES)
def test_error_has_code_attribute(cls) -> None:
    assert hasattr(cls, "code")
    assert isinstance(cls.code, str)
    assert cls.code  # non-empty


@pytest.mark.parametrize("cls", _ALL_ERROR_CLASSES)
def test_to_payload_returns_code_and_message(cls) -> None:
    err = cls("something went wrong")
    payload = err.to_payload()
    assert "code" in payload
    assert "message" in payload
    assert payload["code"] == cls.code
    assert "something went wrong" in payload["message"]


@pytest.mark.parametrize("cls", _NEW_CLASSES)
def test_new_error_classes_are_present(cls) -> None:
    err = cls("test")
    assert isinstance(err, McpServerError)
    assert err.to_payload()["code"] == cls.code


def test_mcp_server_error_is_exception() -> None:
    with pytest.raises(McpServerError):
        raise McpServerError("base error")


def test_each_subclass_has_unique_code() -> None:
    codes = [cls.code for cls in _ALL_ERROR_CLASSES]
    assert len(codes) == len(set(codes)), "Duplicate error codes found"
