"""Strict URI parsing for code-intelligence resources."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from llm_sca_tooling.mcp_server.errors import ResourceInvalidUri, ToolInvalidArguments

__all__ = ["ParsedResourceUri", "parse_resource_uri", "validate_relative_path"]


@dataclass(frozen=True)
class ParsedResourceUri:
    uri: str
    resource: str
    segments: tuple[str, ...]


def _reject_unsafe_segment(segment: str) -> None:
    if segment in {"", ".", ".."}:
        raise ResourceInvalidUri("resource URI contains an unsafe path segment")
    if "\\" in segment:
        raise ResourceInvalidUri("resource URI contains an unsafe path separator")


def validate_relative_path(path: str, *, for_tool: bool = False) -> str:
    """Validate a repo-relative path supplied by a resource URI or tool."""
    normalized = path.replace("\\", "/")
    error_cls = ToolInvalidArguments if for_tool else ResourceInvalidUri
    if (
        normalized.startswith("/")
        or normalized.startswith("../")
        or "/../" in normalized
    ):
        raise error_cls("path traversal is not allowed", {"path": path})
    if normalized in {"", ".", ".."}:
        raise error_cls("path must be repo-relative", {"path": path})
    return normalized


def parse_resource_uri(uri: str) -> ParsedResourceUri:
    parsed = urlsplit(uri)
    if parsed.scheme != "code-intelligence":
        raise ResourceInvalidUri("unsupported resource URI scheme", {"uri": uri})
    if not parsed.netloc:
        raise ResourceInvalidUri("resource URI must include an authority", {"uri": uri})

    raw_segments = [parsed.netloc, *[p for p in parsed.path.split("/") if p]]
    segments = tuple(unquote(s) for s in raw_segments)
    for segment in segments:
        _reject_unsafe_segment(segment)
    return ParsedResourceUri(uri=uri, resource=segments[0], segments=segments)
