"""Tests for the MCP patch-review tool handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tools.patch_review import (
    ClassifyPatchRiskTool,
    RunPatchReviewTool,
)


def _context(tmp_path: Path):
    ctx = MagicMock()
    ctx.workspace.artifact_root = tmp_path
    ctx.workspace.artifacts.record_artifact.side_effect = lambda ref, **kwargs: ref
    return ctx


def test_run_patch_review_tool_call(safe_diff: str, tmp_path: Path) -> None:
    tool = RunPatchReviewTool()
    ctx = _context(tmp_path)
    result = tool.call(ctx, {"diff": safe_diff, "run_id": "r1"})
    assert result.tool_name == "run_patch_review"
    assert result.status == "completed"
    assert "report" in result.payload
    assert "harness_condition" in result.payload
    assert result.artifact_refs


def test_classify_patch_risk_tool_call(safe_diff: str, tmp_path: Path) -> None:
    tool = ClassifyPatchRiskTool()
    ctx = _context(tmp_path)
    result = tool.call(ctx, {"diff": safe_diff})
    assert result.tool_name == "classify_patch_risk"
    assert result.status == "completed"
    assert "risk_result" in result.payload
    assert result.artifact_refs


def test_invalid_diff_raises() -> None:
    tool = RunPatchReviewTool()
    with pytest.raises(ToolInvalidArguments):
        tool.call(MagicMock(), {})


def test_invalid_optional_types_raise(safe_diff: str, tmp_path: Path) -> None:
    tool = RunPatchReviewTool()
    ctx = _context(tmp_path)
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"diff": safe_diff, "sarif_appeared": "nope"})
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"diff": safe_diff, "test_results_before": "nope"})
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"diff": safe_diff, "allowlisted_paths": "nope"})
    with pytest.raises(ToolInvalidArguments):
        tool.call(ctx, {"diff": safe_diff, "run_id": 123})


def test_classify_invalid_diff_raises(tmp_path: Path) -> None:
    tool = ClassifyPatchRiskTool()
    with pytest.raises(ToolInvalidArguments):
        tool.call(MagicMock(), {"diff": ""})
