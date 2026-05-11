"""JSON-RPC framing helpers for LSP stdio."""

from __future__ import annotations

from typing import Any

import orjson

__all__ = ["encode_message", "decode_header"]


def encode_message(payload: dict[str, Any]) -> bytes:
    body = orjson.dumps(payload)
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def decode_header(header: bytes) -> int:
    text = header.decode(errors="replace")
    for line in text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("missing Content-Length header")
