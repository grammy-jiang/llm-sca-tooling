"""relabel_trajectory MCP tool (Agent-HER hindsight relabelling parity).

The last LLM boundary without an MCP surface: a stored trajectory can now be
hindsight-relabelled as a candidate demonstration for a new goal, under the
memory policy guard, with llm_mode driving the LLM relabeller when available.
"""

from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig

ISSUE_HASH = "hash:nulldereference"


async def _server(tmp_path: Path) -> MCPServer:
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize(client_capabilities={})
    return server


async def _seed_trajectory(server: MCPServer) -> str:
    result = await server.call_tool(
        "record_trajectory",
        {
            "trajectory_id": "traj:seed",
            "repo_id": "repo:test",
            "workflow_type": "bug_resolve",
            "issue_class": "null-deref",
            "issue_text_hash": ISSUE_HASH,
            "outcome": "no_fix_found",
            "source_run_id": "run:seed",
        },
    )
    assert result.status == "completed"
    return "traj:seed"


def _set_policy(server: MCPServer, *, allow_relabel: bool) -> None:
    store = server._require_context().memory
    store.policy = store.policy.model_copy(
        update={
            "enabled": True,
            "allow_hindsight_relabelling": allow_relabel,
        }
    )


async def test_relabel_rejected_when_policy_disallows(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    _set_policy(server, allow_relabel=False)
    tid = await _seed_trajectory(server)
    result = await server.call_tool(
        "relabel_trajectory",
        {"trajectory_id": tid, "candidate_goal": "sibling fix"},
    )
    assert result.status == "rejected"
    assert result.payload["status"] == "relabelling_not_allowed"


async def test_relabel_missing_trajectory(tmp_path: Path) -> None:
    server = await _server(tmp_path)
    _set_policy(server, allow_relabel=True)
    result = await server.call_tool(
        "relabel_trajectory",
        {"trajectory_id": "traj:nope", "candidate_goal": "x"},
    )
    assert result.status == "rejected"
    assert result.payload["status"] == "trajectory_not_found"


async def test_relabel_null_mode_stores_unreviewed_hypothesis(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    server = await _server(tmp_path)
    _set_policy(server, allow_relabel=True)
    tid = await _seed_trajectory(server)
    result = await server.call_tool(
        "relabel_trajectory",
        {"trajectory_id": tid, "candidate_goal": "sibling fix", "llm_mode": True},
    )
    assert result.status == "completed"
    assert result.payload["llm_mode_active"] is False  # no provider -> null
    new_record = result.payload["relabelled_trajectory"]
    assert new_record["relabelled"] is True
    assert new_record["review_state"] == "unreviewed"
    assert new_record["trajectory_id"] != tid
    # Original is untouched.
    store = server._require_context().memory
    original = store.get_trajectory(tid)
    assert original is not None
    assert original.relabelled is False


async def test_relabel_llm_mode_active_with_fake_provider(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_factory(*args, **kwargs):
        return lambda prompt: json.dumps(
            {"relabelled_outcome": "resolved", "relabelled_utility": "medium"}
        )

    monkeypatch.setattr("llm_sca_tooling.llm.get_completion_callable", fake_factory)
    server = await _server(tmp_path)
    _set_policy(server, allow_relabel=True)
    tid = await _seed_trajectory(server)
    result = await server.call_tool(
        "relabel_trajectory",
        {"trajectory_id": tid, "candidate_goal": "sibling fix", "llm_mode": True},
    )
    assert result.status == "completed"
    assert result.payload["llm_mode_active"] is True
