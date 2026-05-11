"""Tests for deterministic indexing hash helpers."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.indexing.hashing import hash_content, hash_str


def test_hash_content_uses_sha256_bytes() -> None:
    content = b"phase-3-indexing"

    assert hash_content(content) == hashlib.sha256(content).hexdigest()


def test_hash_str_uses_utf8_sha256() -> None:
    value = "phase-3-indexing"

    assert hash_str(value) == hashlib.sha256(value.encode()).hexdigest()
