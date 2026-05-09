"""LSP/JSON-RPC framing helpers."""

from __future__ import annotations

import json


def encode_message(payload: dict) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def decode_header(header: bytes) -> int:
    for line in header.decode("ascii").split("\r\n"):
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("Content-Length header missing")
