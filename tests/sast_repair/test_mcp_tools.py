"""Tests for sast_repair MCP tool handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tools.sast_repair import (
    EvolveStaticRulesTool,
    GetPredicateExamplesTool,
    RunSastRepairTool,
)


def _ctx(tmp_path: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.workspace.artifact_root = tmp_path
    ctx.workspace.artifacts.record_artifact.side_effect = lambda ref, **kwargs: ref
    return ctx


def test_get_predicate_examples_tool(corpus_root: Path, tmp_path: Path) -> None:
    tool = GetPredicateExamplesTool()
    ctx = _ctx(tmp_path)
    result = tool.call(
        ctx,
        {
            "rule_id": "py.nullderef",
            "corpus_root": str(corpus_root),
            "k": 3,
        },
    )
    assert result.tool_name == "get_predicate_examples"
    assert result.status == "completed"
    assert result.payload["examples"]
    assert result.artifact_refs


def test_get_predicate_examples_requires_rule_id(
    corpus_root: Path, tmp_path: Path
) -> None:
    tool = GetPredicateExamplesTool()
    ctx = _ctx(tmp_path)
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"corpus_root": str(corpus_root)})


def test_get_predicate_examples_requires_corpus_root(tmp_path: Path) -> None:
    tool = GetPredicateExamplesTool()
    ctx = _ctx(tmp_path)
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"rule_id": "py.nullderef"})


def test_run_sast_repair_tool_call(
    corpus_root: Path, tmp_path: Path, nullderef_alert: dict
) -> None:
    tool = RunSastRepairTool()
    ctx = _ctx(tmp_path)
    result = tool.call(
        ctx,
        {
            "alert": nullderef_alert,
            "corpus_root": str(corpus_root),
            "before_alerts": [{"alert_id": "alert-nullderef-001"}],
            "after_alerts": [],
            "classification_signals": {"has_dataflow_edges": True},
            "null_mode": True,
            "run_id": "r1",
        },
    )
    assert result.tool_name == "run_sast_repair"
    assert result.status == "completed"
    assert "report" in result.payload
    assert "harness_condition" in result.payload
    assert result.artifact_refs


def test_run_sast_repair_tool_requires_alert(corpus_root: Path, tmp_path: Path) -> None:
    tool = RunSastRepairTool()
    ctx = _ctx(tmp_path)
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"corpus_root": str(corpus_root)})


def test_evolve_static_rules_tool_returns_offline_candidate(tmp_path: Path) -> None:
    tool = EvolveStaticRulesTool()
    ctx = _ctx(tmp_path)
    result = tool.call(
        ctx,
        {"sarif_deltas": [{"rule_id": "r1", "classification": "false_positive"}]},
    )
    assert result.status == "completed"
    assert result.payload["status"] == "candidate_generated"
    assert any(d["code"] == "offline_validation_required" for d in result.diagnostics)
