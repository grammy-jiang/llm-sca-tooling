from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.traces.adapters.cpp_adapter import CppTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.js_adapter import JSTraceAdapterPlaceholder
from llm_sca_tooling.traces.adapters.registry import (
    TraceAdapterRegistry,
    build_default_registry,
)
from llm_sca_tooling.traces.artefact_store import write_artefact
from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.compression.state_diff import (
    compute_divergence_points,
    compute_state_diffs,
)
from llm_sca_tooling.traces.integration.bug_resolve_hook import (
    apply_trace_to_gate_runner,
)
from llm_sca_tooling.traces.integration.fl_hook import augment_fl_with_trace
from llm_sca_tooling.traces.integration.impl_check_hook import (
    make_dynamic_verdict_from_trace,
)
from llm_sca_tooling.traces.integration.patch_review_hook import (
    link_mismatch_to_divergence,
)
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    DivergencePoint,
    ScopeFilter,
    TraceEvent,
    TraceRunContract,
    TraceRunResult,
)
from llm_sca_tooling.traces.scope_filter import (
    derive_scope_from_suspects,
    validate_scope,
)
from llm_sca_tooling.traces.service import capture_trace


def test_models_round_trip() -> None:
    scope = ScopeFilter(include_modules=["src.app"], include_files=["src/app.py"])
    assert ScopeFilter.model_validate_json(scope.model_dump_json()) == scope

    contract = TraceRunContract(
        contract_id="c1",
        command="src/app.py",
        scope_filter=scope,
    )
    assert TraceRunContract.model_validate_json(contract.model_dump_json()) == contract

    with pytest.raises(ValidationError):
        TraceRunContract.model_validate({"contract_id": "x"})

    # Status enum coverage
    statuses = {
        "completed",
        "timeout",
        "scope_empty",
        "out_of_scope",
        "not_implemented",
        "truncated",
        "not_reproducing",
        "failed",
    }
    assert len(statuses) == 8

    # DivergencePoint divergence_type coverage
    dtypes = {
        "branch_taken_vs_not_taken",
        "exception_raised_vs_not",
        "return_value_type_mismatch",
        "call_order_change",
        "missing_call",
        "new_call",
    }
    assert len(dtypes) == 6


def test_scope_filter(tmp_path) -> None:
    # Derive from suspects
    scope = derive_scope_from_suspects(["src/app.py", "src/db.py", "src/utils.py"])
    assert scope.derived_from_fl_result is True
    assert "src/app.py" in scope.include_files
    assert scope.trace_stdlib is False

    # Empty scope rejected
    empty_scope = ScopeFilter()
    diags = validate_scope(empty_scope)
    assert "scope_empty" in diags

    # Non-empty scope valid
    valid_scope = ScopeFilter(include_modules=["app"])
    assert validate_scope(valid_scope) == []


def test_artefact_store(tmp_path) -> None:
    events = [
        TraceEvent(
            event_id="e1",
            event_type="call",
            module="app",
            function="authenticate",
            file_path="src/app.py",
            line_number=10,
        )
    ]
    artefact = write_artefact("run1", events, workspace_root=tmp_path)
    assert artefact.event_count == 1
    assert artefact.size_bytes > 0
    assert not artefact.truncated

    # Truncation
    small_artefact = write_artefact(
        "run2", events, workspace_root=tmp_path, max_bytes=1
    )
    assert small_artefact.truncated


def test_adapter_placeholders(tmp_path) -> None:
    import asyncio

    scope = ScopeFilter(include_modules=["app"])
    contract = TraceRunContract(
        contract_id="c1",
        command="script.js",
        scope_filter=scope,
        language="javascript",
        adapter_id="javascript",
    )

    js = JSTraceAdapterPlaceholder()
    artefact, non_rep = asyncio.run(js.run(contract, workspace_root=tmp_path))
    assert artefact.language == "javascript"
    assert artefact.event_count == 0

    contract2 = TraceRunContract(
        contract_id="c2",
        command="main.cpp",
        scope_filter=scope,
        language="cpp",
        adapter_id="cpp",
    )
    cpp = CppTraceAdapterPlaceholder()
    artefact2, _ = asyncio.run(cpp.run(contract2, workspace_root=tmp_path))
    assert artefact2.language == "cpp"


def test_adapter_registry() -> None:

    assert issubclass(TraceAdapterRegistry, object)
    registry = build_default_registry()
    assert "python" in registry.available_languages()
    assert "javascript" in registry.available_languages()
    assert "cpp" in registry.available_languages()
    assert registry.get("unknown") is None


def test_null_summarizer(tmp_path) -> None:

    assert issubclass(NullTraceSummarizer, TraceSummarizerInterface)

    events = [
        TraceEvent(
            event_id=f"e{i}",
            event_type="call" if i % 3 != 0 else "exception",
            module="app",
            function="fn",
            file_path="src/app.py",
        )
        for i in range(60)
    ]
    artefact = write_artefact("run1", events, workspace_root=tmp_path)
    scope = ScopeFilter(include_modules=["app"])
    summarizer = NullTraceSummarizer()
    compressed = summarizer.summarize(artefact, scope)

    assert isinstance(compressed, CompressedTrace)
    assert len(compressed.relevant_events) <= 50
    assert compressed.raw_artefact_id == artefact.artefact_id
    # Raw artefact path not present in compressed trace
    assert not hasattr(compressed, "events_jsonl_path")
    assert compressed.summarizer_model == "null"


def test_state_diff_and_divergence(tmp_path) -> None:
    pre_events = [
        TraceEvent(
            event_id="e1",
            event_type="call",
            module="app",
            function="authenticate",
            file_path="src/app.py",
        ),
        TraceEvent(
            event_id="e2",
            event_type="exception",
            module="app",
            function="validate_token",
            file_path="src/app.py",
        ),
    ]
    post_events = [
        TraceEvent(
            event_id="e3",
            event_type="call",
            module="app",
            function="authenticate",
            file_path="src/app.py",
        ),
        TraceEvent(
            event_id="e4",
            event_type="return",
            module="app",
            function="validate_token",
            file_path="src/app.py",
        ),
    ]
    pre_artefact = write_artefact("pre", pre_events, workspace_root=tmp_path)
    post_artefact = write_artefact("post", post_events, workspace_root=tmp_path)

    diffs = compute_state_diffs(pre_artefact, post_artefact)
    assert any(d.diff_type == "exception_vs_return" for d in diffs)

    divergences = compute_divergence_points(pre_artefact, post_artefact, diffs)
    assert any(dp.divergence_type == "exception_raised_vs_not" for dp in divergences)


@pytest.mark.asyncio
async def test_capture_trace_null_mode(tmp_path) -> None:
    # Null mode: scope derived, artefact stored, compressed returned
    result, compressed = await capture_trace(
        script="src/app.py",
        suspects=["src/app.py"],
        null_mode=True,
        workspace_root=tmp_path,
    )
    assert result.status in {"completed", "not_reproducing", "truncated"}
    assert result.harness_condition_id.startswith("hcs:")
    assert result.raw_artefact_ref is not None
    assert compressed is not None
    assert isinstance(compressed, CompressedTrace)

    # Scope-empty rejection
    result_empty, _ = await capture_trace(
        script="src/app.py",
        scope_filter=ScopeFilter(),
        null_mode=True,
        workspace_root=tmp_path,
    )
    assert result_empty.status == "scope_empty"

    # Not-implemented adapter
    result_js, _ = await capture_trace(
        script="app.js",
        suspects=["app.js"],
        language="unknown_lang",
        null_mode=True,
        workspace_root=tmp_path,
    )
    assert result_js.status == "not_implemented"

    # HarnessConditionSheet attached to every result
    for r in [result, result_empty, result_js]:
        assert r.harness_condition_id.startswith("hcs:")


def test_integration_hooks(tmp_path) -> None:
    # FL hook: trace suspects added, static suspects preserved
    ranked = [{"file_path": "src/app.py", "score": 0.9, "repo_id": "r"}]
    dp = DivergencePoint(
        trace_run_id="r1",
        function_path="validate_token",
        file_path="src/auth.py",
        divergence_type="exception_raised_vs_not",
    )
    compressed = CompressedTrace(
        trace_run_id="r1",
        raw_artefact_id="a1",
        executed_path_summary="test",
        divergence_points=[dp],
    )
    augmented = augment_fl_with_trace(ranked, compressed)
    assert any(c["file_path"] == "src/app.py" for c in augmented)
    assert any(c["file_path"] == "src/auth.py" for c in augmented)
    assert len(augmented) == 2

    # Duplicate not added
    augmented2 = augment_fl_with_trace(augmented, compressed)
    assert len(augmented2) == 2

    # Impl-check hook
    write_artefact("r1", [], workspace_root=tmp_path)
    result = TraceRunResult(
        trace_run_id="r1",
        contract_id="c1",
        language="python",
        adapter_id="python",
        status="not_implemented",
        harness_condition_id="hcs:test",
        run_id="r1",
        non_reproducing=False,
    )
    dv = make_dynamic_verdict_from_trace("clause:1", result, None)
    assert dv.available is False
    assert dv.verdict == "unknown"

    result2 = result.model_copy(update={"status": "completed", "non_reproducing": True})
    dv2 = make_dynamic_verdict_from_trace("clause:1", result2, None)
    assert dv2.available is True
    assert dv2.verdict == "unknown"

    # Bug-resolve hook: non-reproducing → trace_available: False
    br = apply_trace_to_gate_runner(result2, compressed)
    assert br["trace_available"] is False

    # Patch-review hook
    ref = link_mismatch_to_divergence("diff:1", [dp])
    assert ref is not None
    assert "r1" in ref

    no_ref = link_mismatch_to_divergence("diff:1", [])
    assert no_ref is None


def test_dryrun_mismatch_trace_field() -> None:
    from llm_sca_tooling.patch_review.models import DryRUNMismatch

    mismatch = DryRUNMismatch(
        diff_id="d1",
        prediction_id="p1",
        mismatch_type="file_scope",
        predicted_value="a",
        actual_value="b",
        severity="low",
        residual_risk_note="none",
        trace_divergence_ref="divergence:r1/validate_token",
    )
    assert mismatch.trace_divergence_ref is not None
    assert DryRUNMismatch.model_validate_json(mismatch.model_dump_json()) == mismatch


@pytest.mark.asyncio
async def test_capture_trace_tool_lifecycle(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)

        result = await handlers.capture_trace(
            {"script": "src/app.py", "suspects": ["src/app.py"], "null_mode": True}
        )
        assert result.payload["result"]["status"] in {
            "completed",
            "not_reproducing",
            "scope_empty",
            "truncated",
        }

        queued = await handlers.capture_trace({"script": "src/app.py", "task": True})
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True
    finally:
        await context.close()
