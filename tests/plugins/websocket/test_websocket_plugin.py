from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.storage import initialize_workspace


def test_websocket_plugin_emits_event_edges(tmp_path: Path) -> None:
    root = tmp_path / "ws_repo"
    root.mkdir()
    (root / "server.py").write_text("from flask_socketio import SocketIO\nsocketio = SocketIO()\n\n@socketio.on('message', namespace='/chat')\ndef handle_message(data):\n    pass\n", encoding="utf-8")
    (root / "client.ts").write_text("import { io } from 'socket.io-client';\nconst socket = io('/chat');\nsocket.emit('message', {text: 'hi'});\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    workspace = initialize_workspace(tmp_path / "workspace")
    try:
        result = IndexingService(workspace).graph_build(root)
        assert workspace.graph.fetch_nodes_by_type(result.repo_id, GraphNodeType.WEBSOCKET_EVENT)
        assert workspace.graph.fetch_edges_by_type(result.repo_id, GraphEdgeType.EXPOSES)
        assert workspace.graph.fetch_edges_by_type(result.repo_id, GraphEdgeType.CONSUMES)
    finally:
        workspace.close()
