"""Tests for WebSocket plugin IMPLEMENTS and FFI edge emission."""

from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.plugins.websocket.plugin import WebSocketPlugin
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.storage import initialize_workspace


def _build_ws_repo(root: Path) -> None:
    (root / "server.py").write_text(
        "from flask_socketio import SocketIO\n"
        "socketio = SocketIO()\n\n"
        "@socketio.on('message', namespace='/chat')\n"
        "def handle_message(data):\n"
        "    pass\n",
        encoding="utf-8",
    )
    (root / "client.ts").write_text(
        "import { io } from 'socket.io-client';\n"
        "const socket = io('/chat');\n"
        "socket.on('message', (data) => { console.log(data); });\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "commit",
            "-m",
            "init",
        ],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def test_websocket_plugin_describes_implements_and_ffi() -> None:
    cap = WebSocketPlugin().describe_capability()
    assert GraphEdgeType.IMPLEMENTS in cap.emitted_edge_types
    assert GraphEdgeType.FFI in cap.emitted_edge_types


def test_websocket_plugin_emits_implements_edges(tmp_path: Path) -> None:
    root = tmp_path / "ws_repo"
    root.mkdir()
    _build_ws_repo(root)
    workspace = initialize_workspace(tmp_path / "workspace")
    try:
        result = IndexingService(workspace).graph_build(root)
        implements_edges = workspace.graph.fetch_edges_by_type(
            result.repo_id, GraphEdgeType.IMPLEMENTS
        )
        assert (
            implements_edges
        ), "Expected at least one IMPLEMENTS edge from server handler to event node"
    finally:
        workspace.close()


def test_websocket_plugin_emits_ffi_edges_server_to_client(tmp_path: Path) -> None:
    root = tmp_path / "ws_repo"
    root.mkdir()
    _build_ws_repo(root)
    workspace = initialize_workspace(tmp_path / "workspace")
    try:
        result = IndexingService(workspace).graph_build(root)
        ffi_edges = workspace.graph.fetch_edges_by_type(
            result.repo_id, GraphEdgeType.FFI
        )
        assert (
            ffi_edges
        ), "Expected FFI edges from server handler nodes to client handler nodes"
    finally:
        workspace.close()
