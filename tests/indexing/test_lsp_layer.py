from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.backends.cpp.clangd_adapter import ClangdAdapter
from llm_sca_tooling.indexing.backends.python.pyright_adapter import PyrightAdapter
from llm_sca_tooling.indexing.hashing import hash_file
from llm_sca_tooling.indexing.lsp import LspClient, LspTimeout
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    GraphEdgeType,
    GraphNodeType,
    IndexStatus,
    Severity,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


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


def test_lsp_client_collects_publish_diagnostics(tmp_path: Path) -> None:
    server = _write_diagnostic_lsp_server(tmp_path)
    source = tmp_path / "example.py"
    source.write_text("x: int = 'bad'\n", encoding="utf-8")
    client = LspClient("mock", [sys.executable, str(server)], tmp_path)
    client.start(timeout_ms=1000)
    try:
        client.open_document(
            source.as_uri(), "python", source.read_text(encoding="utf-8")
        )
        notification = client.wait_for_notification(
            "textDocument/publishDiagnostics", timeout_ms=1000
        )
        assert notification is not None
        assert notification["params"]["diagnostics"][0]["code"] == "mock-rule"
    finally:
        client.stop()


def test_pyright_adapter_converts_lsp_diagnostics(tmp_path: Path) -> None:
    server = _write_diagnostic_lsp_server(tmp_path)
    source = tmp_path / "example.py"
    source.write_text("x: int = 'bad'\n", encoding="utf-8")
    scanned = _scanned_file(tmp_path, source, "python")
    adapter = PyrightAdapter([sys.executable, str(server)], diagnostic_timeout_ms=1000)
    result = adapter.index_files(
        tmp_path, _repo(), _snapshot(), [scanned], run_id="run:test"
    )
    assert any(
        diagnostic.code == "mock-rule" and diagnostic.severity == Severity.ERROR
        for diagnostic in result.diagnostics
    )
    assert any(node.node_type == GraphNodeType.SAST_RULE for node in result.nodes)
    assert any(edge.edge_type == GraphEdgeType.WARNED_BY for edge in result.edges)


def test_clangd_adapter_converts_lsp_diagnostics(tmp_path: Path) -> None:
    server = _write_diagnostic_lsp_server(tmp_path)
    source = tmp_path / "main.cpp"
    source.write_text("int main() { return missing; }\n", encoding="utf-8")
    scanned = _scanned_file(tmp_path, source, "cpp")
    adapter = ClangdAdapter([sys.executable, str(server)], diagnostic_timeout_ms=1000)
    result = adapter.index_files(
        tmp_path, _repo(), _snapshot(), [scanned], run_id="run:test"
    )
    assert any(
        diagnostic.code == "mock-rule" and diagnostic.severity == Severity.ERROR
        for diagnostic in result.diagnostics
    )
    assert any(node.node_type == GraphNodeType.SAST_RULE for node in result.nodes)
    assert any(edge.edge_type == GraphEdgeType.WARNED_BY for edge in result.edges)


def _write_diagnostic_lsp_server(tmp_path: Path) -> Path:
    server = tmp_path / "mock_diagnostic_lsp.py"
    server.write_text(
        """
import json, sys
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
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{'capabilities':{'textDocumentSync': 1}}})
    elif msg.get('method') == 'textDocument/didOpen':
        uri = msg['params']['textDocument']['uri']
        write_msg({'jsonrpc':'2.0','method':'textDocument/publishDiagnostics','params':{'uri': uri, 'diagnostics':[{'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':1}},'severity':1,'code':'mock-rule','source':'mock-lsp','message':'mock diagnostic'}]}})
    elif msg.get('method') == 'shutdown':
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{}})
    elif 'id' in msg:
        write_msg({'jsonrpc':'2.0','id':msg['id'],'result':{}})
""",
        encoding="utf-8",
    )
    return server


def _repo() -> RepoRef:
    return RepoRef(repo_id="repo:test", name="test", root_ref="root")


def _snapshot() -> SnapshotRef:
    return SnapshotRef(
        repo_id="repo:test",
        worktree_snapshot_id="worktree:test",
        dirty=True,
        index_status=IndexStatus.FRESH,
        captured_ts=_now_ts(),
    )


def _scanned_file(repo_root: Path, path: Path, language: str) -> ScannedFile:
    return ScannedFile(
        path=path.relative_to(repo_root).as_posix(),
        abs_path=path,
        language=language,
        size_bytes=path.stat().st_size,
        sha256=hash_file(path),
        is_test=False,
        is_generated=False,
    )
