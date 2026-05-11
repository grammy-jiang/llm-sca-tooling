"""Phase 5 LSP abstraction tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.lsp.client import LspClient
from llm_sca_tooling.indexing.lsp.errors import LspError, LspTimeout
from llm_sca_tooling.indexing.lsp.lifecycle import LspClient as LifecycleLspClient
from llm_sca_tooling.indexing.lsp.protocol import decode_header, encode_message
from llm_sca_tooling.indexing.lsp.request_dispatcher import (
    LspClient as DispatcherLspClient,
)


async def test_lsp_client_start_request_notify_and_stop(tmp_path: Path) -> None:
    server = _write_mock_server(tmp_path, "normal")
    client = LspClient("mock", [sys.executable, str(server)], tmp_path)

    await client.start()
    assert client.server_capabilities == {"definitionProvider": True}
    assert await client.request("custom/echo", {"value": 7}, timeout_ms=1_000) == {
        "echo": {"value": 7}
    }
    await client.open_document((tmp_path / "file.py").as_uri(), "python", "x = 1")
    await client.close_document((tmp_path / "file.py").as_uri())
    await client.stop()


async def test_lsp_client_timeout_raises(tmp_path: Path) -> None:
    server = _write_mock_server(tmp_path, "slow")
    client = LspClient("slow", [sys.executable, str(server)], tmp_path)
    await client.start()

    with pytest.raises(LspTimeout):
        await client.request("custom/slow", {}, timeout_ms=50)

    await client.stop()


async def test_lsp_client_crash_raises_lsp_error(tmp_path: Path) -> None:
    server = _write_mock_server(tmp_path, "crash_after_initialize")
    client = LspClient("crash", [sys.executable, str(server)], tmp_path)
    await client.start()

    with pytest.raises(LspError, match="crashed"):
        await client.request("custom/echo", {}, timeout_ms=1_000)

    await client.stop()


def test_lsp_protocol_decode_header_rejects_missing_content_length() -> None:
    assert encode_message({"jsonrpc": "2.0"}).startswith(b"Content-Length:")
    assert LifecycleLspClient is LspClient
    assert DispatcherLspClient is LspClient
    with pytest.raises(ValueError, match="missing Content-Length"):
        decode_header(b"X-Test: 1\r\n\r\n")


def _write_mock_server(tmp_path: Path, mode: str) -> Path:
    script = tmp_path / f"mock_lsp_{mode}.py"
    script.write_text(f"""
import json
import sys
import time

MODE = {mode!r}


def read_message():
    header = b""
    while not header.endswith(b"\\r\\n\\r\\n"):
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
    length = 0
    for line in header.decode().split("\\r\\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
    return json.loads(sys.stdin.buffer.read(length))


def write_message(payload):
    body = json.dumps(payload).encode()
    sys.stdout.buffer.write(f"Content-Length: {{len(body)}}\\r\\n\\r\\n".encode() + body)
    sys.stdout.buffer.flush()


while True:
    message = read_message()
    if message is None:
        break
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        write_message({{"jsonrpc": "2.0", "id": request_id, "result": {{"capabilities": {{"definitionProvider": True}}}}}})
        if MODE == "crash_after_initialize":
            next_message = read_message()
            if next_message is not None and next_message.get("method") == "initialized":
                sys.exit(1)
    elif request_id is None:
        continue
    elif method == "shutdown":
        write_message({{"jsonrpc": "2.0", "id": request_id, "result": {{}}}})
    elif method == "custom/slow":
        time.sleep(1)
        write_message({{"jsonrpc": "2.0", "id": request_id, "result": {{}}}})
    elif method == "custom/echo":
        write_message({{"jsonrpc": "2.0", "id": request_id, "result": {{"echo": message.get("params")}}}})
    else:
        write_message({{"jsonrpc": "2.0", "id": request_id, "result": {{}}}})
""")
    return script
