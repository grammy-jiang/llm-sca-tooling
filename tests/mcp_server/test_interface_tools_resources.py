from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


def test_trace_cross_language_and_interface_resources(tmp_path: Path) -> None:
    repo = _phase7_http_repo(tmp_path)
    server = CodeIntelligenceServer(McpServerConfig.for_workspace(tmp_path / "workspace")).start()
    try:
        build_payload = server.task_result(server.call_tool("graph_build", {"repo_path": str(repo)}).payload["task"]["task_id"])
        interfaces = server.read_resource("code-intelligence://interfaces").payload
        assert interfaces["total_interface_records"] >= 1
        plugin_list = server.read_resource("code-intelligence://interfaces/http-rest").payload
        interface_name = plugin_list["interfaces"][0]["interface_name"]
        record = server.read_resource(f"code-intelligence://interfaces/http-rest/{interface_name}").payload
        assert record["interface_name"] == interface_name
        contract = server.call_tool("get_interface_contract", {"plugin_id": "http-rest", "interface_name": interface_name}).payload
        assert contract["interface_record"]["interface_name"] == interface_name
        assert contract["matched_operations"]
        trace = server.call_tool("trace_cross_language", {"repo": build_payload["repo_id"], "symbol": "api:get_user", "max_hops": 4}).payload
        assert trace["total_hops"] >= 1
        callers = server.call_tool("find_callers", {"repo": build_payload["repo_id"], "symbol": "api:get_user", "include_cross_language": True, "depth": 4}).payload
        assert any(match.get("cross_language") for match in callers["matches"])
    finally:
        server.shutdown()


def _phase7_http_repo(tmp_path: Path) -> Path:
    root = tmp_path / "phase7_http"
    root.mkdir()
    (root / "api.py").write_text("app = object()\n\n@app.get('/users/{id}')\ndef get_user(id: str):\n    return {'id': id}\n", encoding="utf-8")
    (root / "client.ts").write_text("export function loadUser() { return fetch('/users/1'); }\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    return root
