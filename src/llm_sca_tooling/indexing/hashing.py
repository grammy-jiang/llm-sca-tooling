"""File and content hashing utilities for indexing."""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["hash_file", "hash_content", "hash_str", "make_node_id"]


def hash_file(path: Path, *, chunk_size: int = 65_536) -> str:
    """Return the SHA-256 hex digest of a file's content."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def make_node_id(
    repo_id: str,
    node_type: str,
    qualified_name: str,
    file_path: str | None = None,
) -> str:
    """Return a stable, deterministic node ID."""
    key = f"{repo_id}|{node_type}|{qualified_name}|{file_path or ''}"
    return f"node:{hashlib.sha256(key.encode()).hexdigest()[:24]}"


def make_edge_id(
    repo_id: str,
    edge_type: str,
    source_id: str,
    target_id: str,
) -> str:
    key = f"{repo_id}|{edge_type}|{source_id}|{target_id}"
    return f"edge:{hashlib.sha256(key.encode()).hexdigest()[:24]}"
