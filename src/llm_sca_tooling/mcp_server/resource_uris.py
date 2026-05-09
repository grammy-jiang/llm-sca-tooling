"""Strict resource URI parsing."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from llm_sca_tooling.mcp_server.errors import ResourceInvalidUri
from llm_sca_tooling.schemas.base import validate_repo_relative_path

SCHEME = "code-intelligence"


@dataclass(frozen=True)
class ParsedResourceUri:
    uri: str
    authority: str
    segments: tuple[str, ...]


def parse_resource_uri(uri: str) -> ParsedResourceUri:
    parsed = urlparse(uri)
    if parsed.scheme != SCHEME or not parsed.netloc:
        raise ResourceInvalidUri(f"invalid code-intelligence URI: {uri}")
    raw_segments = tuple(segment for segment in parsed.path.split("/") if segment)
    segments = tuple(unquote(segment) for segment in raw_segments)
    for segment in segments:
        if "\\" in segment or segment in {".", ".."}:
            raise ResourceInvalidUri(f"unsafe URI segment: {segment}")
    return ParsedResourceUri(uri=uri, authority=parsed.netloc, segments=segments)


def decode_repo_relative_path(value: str) -> str:
    try:
        return validate_repo_relative_path(unquote(value))
    except ValueError as exc:
        raise ResourceInvalidUri(str(exc)) from exc


def encode_file_path_for_uri(file_path: str) -> str:
    return file_path.replace("/", "%2F")
