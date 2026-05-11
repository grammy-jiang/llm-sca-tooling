"""Canonical JSON helpers for MCP payloads."""

from __future__ import annotations

from typing import Any

import orjson

__all__ = ["canonical_bytes", "canonical_json"]


def canonical_bytes(payload: Any) -> bytes:
    return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)


def canonical_json(payload: Any) -> str:
    return canonical_bytes(payload).decode()
