from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


def test_phase8_qa_tools_and_blame_resource(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def login_handler():\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

    server = CodeIntelligenceServer(McpServerConfig.for_workspace(tmp_path / "workspace")).start()
    try:
        build = server.task_result(server.call_tool("graph_build", {"repo_path": str(repo)}).payload["task"]["task_id"])
        classified = server.call_tool("classify_repo_question", {"question": "Where is `login_handler` defined?", "repos": [build["repo_id"]]}).payload
        assert classified["question_class"] == "file-loc"

        answer = server.call_tool("answer_repo_question", {"question": "Where is `login_handler` defined?", "repos": [build["repo_id"]], "synthesis": False}).payload
        assert answer["confidence"] in {"parser", "analyser", "heuristic"}
        assert answer["evidence"]

        blame = server.call_tool("git_blame_chain", {"repo": build["repo_id"], "file": "app.py", "line": 1}).payload
        assert blame["file_path"] == "app.py"
        assert "entries" in blame
        assert server.resources.is_subscribable(f"code-intelligence://blame/{build['repo_id']}/app.py")
        resource = server.read_resource(f"code-intelligence://blame/{build['repo_id']}/app.py").payload
        assert resource["blame"]["file_path"] == "app.py"
    finally:
        server.shutdown()
