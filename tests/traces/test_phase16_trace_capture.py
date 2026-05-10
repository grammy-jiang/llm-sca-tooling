from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from llm_sca_tooling.mcp_server.tools.traces import CaptureTraceTool
from llm_sca_tooling.traces.compression.state_diff import load_trace_events
from llm_sca_tooling.traces.models import (
    ScopeFilter,
    TraceDivergenceType,
    TraceEvent,
    TraceEventType,
    TraceRunStatus,
)
from llm_sca_tooling.traces.service import capture_trace

FIXTURES = Path(__file__).parent / "fixtures" / "scripts"


async def test_capture_trace_stores_raw_and_returns_compressed(tmp_path: Path) -> None:
    script = FIXTURES / "reproducer_simple.py"
    output = await capture_trace(
        script=str(script),
        working_dir=FIXTURES,
        artifact_root=tmp_path / "artifacts",
        null_mode=True,
    )
    assert output.result.status is TraceRunStatus.COMPLETED
    assert output.raw_artefact is not None
    assert output.compressed_trace is not None
    assert output.result.raw_artefact_ref == output.raw_artefact.artefact_id
    assert output.compressed_trace.raw_artefact_id == output.raw_artefact.artefact_id
    assert "events_jsonl_path" not in output.compressed_trace.model_dump(mode="json")
    assert Path(output.raw_artefact.events_jsonl_path).exists()


async def test_python_adapter_records_exception_events(tmp_path: Path) -> None:
    script = FIXTURES / "reproducer_exception.py"
    output = await capture_trace(
        script=str(script),
        working_dir=FIXTURES,
        artifact_root=tmp_path / "artifacts",
        expected_failure=True,
    )
    assert output.result.status is TraceRunStatus.COMPLETED
    assert output.raw_artefact is not None
    events = load_trace_events(output.raw_artefact.events_jsonl_path)
    assert any(event.event_type is TraceEventType.EXCEPTION for event in events)
    assert output.compressed_trace is not None
    assert output.compressed_trace.exception_events


async def test_non_reproducing_trace_is_uncertainty(tmp_path: Path) -> None:
    script = FIXTURES / "no_reproduce.py"
    output = await capture_trace(
        script=str(script),
        working_dir=FIXTURES,
        artifact_root=tmp_path / "artifacts",
        expected_failure=True,
    )
    assert output.result.status is TraceRunStatus.NOT_REPRODUCING
    assert output.result.non_reproducing is True
    assert output.compressed_trace is not None


async def test_scope_empty_rejected_before_execution(tmp_path: Path) -> None:
    script = FIXTURES / "reproducer_simple.py"
    output = await capture_trace(
        script=str(script),
        working_dir=FIXTURES,
        artifact_root=tmp_path / "artifacts",
        scope_filter=ScopeFilter(include_files=[]),
    )
    assert output.result.status is TraceRunStatus.SCOPE_EMPTY
    assert output.result.raw_artefact_ref is None


async def test_out_of_scope_command_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("print('no trace')\n", encoding="utf-8")
    output = await capture_trace(
        script=str(outside),
        working_dir=root,
        allowed_roots=[root],
        artifact_root=tmp_path / "artifacts",
        scope_filter=ScopeFilter(include_files=["outside.py"]),
    )
    assert output.result.status is TraceRunStatus.OUT_OF_SCOPE
    assert not (tmp_path / "artifacts").exists()


async def test_js_placeholder_is_not_implemented(tmp_path: Path) -> None:
    script = tmp_path / "demo.js"
    script.write_text("console.log('x')\n", encoding="utf-8")
    output = await capture_trace(
        script=str(script),
        working_dir=tmp_path,
        artifact_root=tmp_path / "artifacts",
        language="javascript",
    )
    assert output.result.status is TraceRunStatus.NOT_IMPLEMENTED
    assert output.result.diagnostics[0]["code"] == "js_trace_adapter_not_available"


async def test_truncation_records_status(tmp_path: Path) -> None:
    script = FIXTURES / "reproducer_simple.py"
    output = await capture_trace(
        script=str(script),
        working_dir=FIXTURES,
        artifact_root=tmp_path / "artifacts",
        max_raw_trace_bytes=1,
    )
    assert output.result.status is TraceRunStatus.TRUNCATED
    assert output.raw_artefact is not None
    assert output.raw_artefact.truncated is True


async def test_two_trace_comparison_detects_exception_vs_return(
    tmp_path: Path,
) -> None:
    pre = tmp_path / "pre.py"
    post = tmp_path / "post.py"
    pre.write_text(
        "def target():\n    raise RuntimeError('x')\n\nif __name__ == '__main__':\n    target()\n",
        encoding="utf-8",
    )
    post.write_text(
        "def target():\n    return 1\n\nif __name__ == '__main__':\n    target()\n",
        encoding="utf-8",
    )
    pre_output = await capture_trace(
        script=str(pre),
        working_dir=tmp_path,
        artifact_root=tmp_path / "artifacts",
        expected_failure=True,
    )
    assert pre_output.raw_artefact is not None
    post_output = await capture_trace(
        script=str(post),
        working_dir=tmp_path,
        artifact_root=tmp_path / "artifacts",
        pre_raw_artefact=pre_output.raw_artefact,
    )
    assert post_output.result.state_diffs
    assert any(
        point.divergence_type is TraceDivergenceType.EXCEPTION_RAISED_VS_NOT
        for point in post_output.result.divergence_points
    )


def test_trace_models_round_trip() -> None:
    event = TraceEvent(
        event_id="e1",
        event_type=TraceEventType.CALL,
        module="m",
        function="f",
        file_path="m.py",
        line_number=1,
        depth=0,
        ts_ns=1,
    )
    restored = TraceEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert {status.value for status in TraceRunStatus} == {
        "completed",
        "timeout",
        "scope_empty",
        "out_of_scope",
        "not_implemented",
        "truncated",
        "not_reproducing",
        "failed",
    }


def test_capture_trace_tool_returns_compressed_payload(tmp_path: Path) -> None:
    script = tmp_path / "tool_script.py"
    script.write_text("def target():\n    return 1\n\ntarget()\n", encoding="utf-8")
    ctx = MagicMock()
    ctx.workspace.artifact_root = tmp_path / "artifacts"
    ctx.workspace.artifacts.record_artifact.side_effect = lambda ref, **_kwargs: ref
    ctx.workspace.graph = None
    ctx.authorization_context_hash = None
    tool = CaptureTraceTool()
    result = tool.call(ctx, {"script": str(script), "repo_path": str(tmp_path)})
    assert result.tool_name == "capture_trace"
    assert result.status == "completed"
    assert "compressed_trace" in result.payload
    assert "harness_condition" in result.payload
    assert result.artifact_refs
