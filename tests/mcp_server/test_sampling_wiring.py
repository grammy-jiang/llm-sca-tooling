"""Tests for McpSamplingClient and patch generator wiring in MCP tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.mcp_sampling_client import McpSamplingClient
from llm_sca_tooling.mcp_server.tools.issue_resolution import RunIssueResolutionTool
from llm_sca_tooling.mcp_server.tools.sast_repair import RunSastRepairTool
from llm_sca_tooling.sast_repair.patch_generator import (
    SamplingPatchGenerator,
)
from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    NullCandidatePatchGenerator,
    SamplingCandidatePatchGenerator,
)

# ---------------------------------------------------------------------------
# McpRequestContext sampling_client propagation
# ---------------------------------------------------------------------------


def test_mcp_request_context_default_sampling_client_none() -> None:
    ctx = MagicMock(spec=McpRequestContext)
    ctx.sampling_client = None
    assert ctx.sampling_client is None


def test_mcp_request_context_with_sampling_client(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from llm_sca_tooling.mcp_server import McpServerConfig

    config = McpServerConfig.for_workspace(tmp_path / "ws")
    ws = MagicMock()
    caps = MagicMock()
    ctx = McpRequestContext(ws, config, caps)
    assert ctx.sampling_client is None

    mock_client = MagicMock()
    ctx2 = ctx.with_sampling_client(mock_client)
    assert ctx2.sampling_client is mock_client
    # original context is not mutated
    assert ctx.sampling_client is None


# ---------------------------------------------------------------------------
# McpSamplingClient
# ---------------------------------------------------------------------------


def test_mcp_sampling_client_available() -> None:
    mock_session = MagicMock()
    loop = asyncio.new_event_loop()
    try:
        client = McpSamplingClient(mock_session, loop)
        assert client.available is True
    finally:
        loop.close()


def test_mcp_sampling_client_create_message_returns_content() -> None:
    """create_message submits to the loop and extracts text from result."""

    async def _fake_create_message(**kwargs):  # type: ignore[override]
        result = MagicMock()
        result.content.text = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-x\n+y"
        return result

    mock_session = MagicMock()
    mock_session.create_message.side_effect = _fake_create_message

    loop = asyncio.new_event_loop()
    try:
        # Run a background thread to keep the loop alive while client.create_message
        # submits the coroutine via run_coroutine_threadsafe.
        import threading

        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            client = McpSamplingClient(mock_session, loop, timeout=5.0)
            result = client.create_message("fix the bug", max_tokens=256)
            assert "content" in result
            assert "--- a/f.py" in result["content"]
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)
    finally:
        loop.close()


def test_mcp_sampling_client_returns_empty_on_exception() -> None:
    async def _bad_session(**kwargs):  # type: ignore[override]
        raise RuntimeError("sampling failed")

    mock_session = MagicMock()
    mock_session.create_message.side_effect = _bad_session

    loop = asyncio.new_event_loop()
    import threading

    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    try:
        client = McpSamplingClient(mock_session, loop, timeout=5.0)
        result = client.create_message("fix it", max_tokens=128)
        assert result == {"content": ""}
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2)
        loop.close()


# ---------------------------------------------------------------------------
# Patch generator wiring in issue_resolution tool
# ---------------------------------------------------------------------------


def _make_ctx(tmp_path: Path, sampling_client=None) -> MagicMock:
    ctx = MagicMock()
    ctx.workspace.artifact_root = tmp_path
    ctx.workspace.artifacts.record_artifact.side_effect = lambda ref, **kwargs: ref
    ctx.sampling_client = sampling_client
    return ctx


def _make_fake_workflow_result() -> tuple:
    """Return a minimal (report, state, trace) tuple using MagicMock."""
    report = MagicMock()
    report.model_dump_json.return_value = "{}"
    report.model_dump.return_value = {}
    state = MagicMock()
    state.status.value = "completed"
    state.stage.value = "done"
    trace = MagicMock()
    trace.run_id = "r-test"
    trace.stage_sequence = []
    return report, state, trace


def test_issue_resolution_null_mode_uses_null_patch_gen(tmp_path: Path) -> None:
    """When null_mode=True, no sampling patch generator is passed to the workflow."""
    tool = RunIssueResolutionTool()
    ctx = _make_ctx(tmp_path, sampling_client=MagicMock())

    captured = {}

    async def _fake_workflow(**kwargs):  # type: ignore[override]
        captured["patch_generator"] = kwargs.get("patch_generator")
        return _make_fake_workflow_result()

    with patch(
        "llm_sca_tooling.mcp_server.tools.issue_resolution.run_bug_resolve_workflow",
        side_effect=_fake_workflow,
    ):
        tool.call(ctx, {"issue_text": "NPE", "null_mode": True})

    assert captured.get("patch_generator") is None


def test_issue_resolution_non_null_mode_uses_sampling_patch_gen(
    tmp_path: Path,
) -> None:
    """When null_mode=False and sampling_client is set, SamplingCandidatePatchGenerator is used."""
    tool = RunIssueResolutionTool()
    mock_client = MagicMock()
    mock_client.available = True
    ctx = _make_ctx(tmp_path, sampling_client=mock_client)

    captured = {}

    async def _fake_workflow(**kwargs):  # type: ignore[override]
        captured["patch_generator"] = kwargs.get("patch_generator")
        return _make_fake_workflow_result()

    with patch(
        "llm_sca_tooling.mcp_server.tools.issue_resolution.run_bug_resolve_workflow",
        side_effect=_fake_workflow,
    ):
        tool.call(ctx, {"issue_text": "NPE", "null_mode": False})

    gen = captured.get("patch_generator")
    assert isinstance(
        gen, SamplingCandidatePatchGenerator
    ), f"expected SamplingCandidatePatchGenerator, got {type(gen)}"


def test_issue_resolution_non_null_mode_no_sampling_client_uses_null(
    tmp_path: Path,
) -> None:
    """When null_mode=False but no sampling_client, None is passed (state machine uses null gen)."""
    tool = RunIssueResolutionTool()
    ctx = _make_ctx(tmp_path, sampling_client=None)

    captured = {}

    async def _fake_workflow(**kwargs):  # type: ignore[override]
        captured["patch_generator"] = kwargs.get("patch_generator")
        return _make_fake_workflow_result()

    with patch(
        "llm_sca_tooling.mcp_server.tools.issue_resolution.run_bug_resolve_workflow",
        side_effect=_fake_workflow,
    ):
        tool.call(ctx, {"issue_text": "NPE", "null_mode": False})

    gen = captured.get("patch_generator")
    # create_patch_generator(None) returns NullCandidatePatchGenerator
    assert isinstance(
        gen, NullCandidatePatchGenerator
    ), f"expected NullCandidatePatchGenerator, got {type(gen)}"


# ---------------------------------------------------------------------------
# Patch generator wiring in sast_repair tool
# ---------------------------------------------------------------------------


def test_sast_repair_generate_patch_false_uses_null_gen(tmp_path: Path) -> None:
    """When generate_patch=False, no patch generator is passed."""
    tool = RunSastRepairTool()
    ctx = _make_ctx(tmp_path, sampling_client=MagicMock())
    alert = {
        "rule_id": "py/null-dereference",
        "location": {"file": "src/x.py", "line": 1},
    }
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()

    captured = {}

    async def _fake_run_sast_repair(**kwargs):  # type: ignore[override]
        captured["patch_generator"] = kwargs.get("patch_generator")
        report = MagicMock()
        report.model_dump.return_value = {}
        report.diagnostics = []
        sheet = MagicMock()
        sheet.model_dump.return_value = {}
        return report, sheet

    import llm_sca_tooling.mcp_server.tools.sast_repair as _mod

    with patch.object(_mod, "run_sast_repair", side_effect=_fake_run_sast_repair):
        tool.call(
            ctx,
            {
                "alert": alert,
                "corpus_root": str(corpus_root),
                "null_mode": True,
                "generate_patch": False,
            },
        )

    assert captured.get("patch_generator") is None


def test_sast_repair_generate_patch_true_uses_sampling_gen(tmp_path: Path) -> None:
    """When generate_patch=True and sampling_client present, SamplingPatchGenerator used."""
    tool = RunSastRepairTool()
    mock_client = MagicMock()
    mock_client.available = True
    ctx = _make_ctx(tmp_path, sampling_client=mock_client)
    alert = {
        "rule_id": "py/null-dereference",
        "location": {"file": "src/x.py", "line": 1},
    }
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()

    captured = {}

    async def _fake_run_sast_repair(**kwargs):  # type: ignore[override]
        captured["patch_generator"] = kwargs.get("patch_generator")
        report = MagicMock()
        report.model_dump.return_value = {}
        report.diagnostics = []
        sheet = MagicMock()
        sheet.model_dump.return_value = {}
        return report, sheet

    import llm_sca_tooling.mcp_server.tools.sast_repair as _mod

    with patch.object(_mod, "run_sast_repair", side_effect=_fake_run_sast_repair):
        tool.call(
            ctx,
            {
                "alert": alert,
                "corpus_root": str(corpus_root),
                "null_mode": True,
                "generate_patch": True,
            },
        )

    gen = captured.get("patch_generator")
    assert isinstance(
        gen, SamplingPatchGenerator
    ), f"expected SamplingPatchGenerator, got {type(gen)}"
