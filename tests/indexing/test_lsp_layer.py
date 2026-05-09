from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.lsp import LspClient, LspTimeout


def test_lsp_client_round_trip_and_timeout(tmp_path: Path) -> None:
    server = tmp_path / "mock_lsp.py"
    server.write_text(
        """
import json, sys, time
def read_msg():
    header = b''
    while b'\\r\\n\\r\\n' not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
    length = int([line for line in header.decode().split('\\r\\n') if line.lower().startswith('content-length')][0].split(':')[1])
    return json.loads(sys.stdin.buffer.read(length).decode())
def write_msg(payload):
    body = json.dumps(payload).encode()
    sys.stdout.buffer.write(f'Content-Length: {len(body)}\\r\\n\\r\\n'.encode() + body)
    sys.stdout.buffer.flush()
while True:
    msg = read_msg()
    if msg is None:
        break
    if msg.get('method') == 'initialize':
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{'capabilities':{'definitionProvider': True}}})
    elif msg.get('method') == 'shutdown':
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{}})
    elif msg.get('method') == 'slow':
        time.sleep(0.2)
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{}})
    elif 'id' in msg:
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{'ok': True}})
""",
        encoding="utf-8",
    )
    client = LspClient("mock", [sys.executable, str(server)], tmp_path)
    client.start(timeout_ms=1000)
    try:
        assert client.server_capabilities.capabilities["definitionProvider"] is True
        assert client.request("custom/test", {}, timeout_ms=1000)["ok"] is True
        with pytest.raises(LspTimeout):
            client.request("slow", {}, timeout_ms=10)
    finally:
        client.stop()
