"""High-level trace capture orchestration."""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.evaluation.harness_condition import (
    HarnessConditionSheet,
    default_harness_condition_sheet,
)
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import ArtifactKind
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.artifacts import ArtifactStore
from llm_sca_tooling.traces.adapters.registry import TraceAdapterRegistry
from llm_sca_tooling.traces.artefact_store import (
    artifact_ref_for_path,
    record_artifact,
    trace_run_dir,
    write_model_json,
)
from llm_sca_tooling.traces.compression.divergence import bind_divergence_points
from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.compression.state_diff import (
    compare_trace_events,
    load_trace_events,
)
from llm_sca_tooling.traces.contract import (
    build_environment_snapshot,
    validate_command_allowlist,
)
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
    TraceLanguage,
    TraceRunContract,
    TraceRunResult,
    TraceRunStatus,
)
from llm_sca_tooling.traces.scope_filter import derive_scope_filter


class TraceCaptureOutput(StrictBaseModel):
    result: TraceRunResult
    compressed_trace: CompressedTrace | None = None
    raw_artefact: RawTraceArtefact | None = None
    harness_condition: HarnessConditionSheet
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


async def capture_trace(
    *,
    script: str,
    args: list[str] | None = None,
    working_dir: str | Path | None = None,
    allowed_roots: list[str | Path] | None = None,
    scope_filter: ScopeFilter | JsonObject | None = None,
    suspects: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    timeout_seconds: int = 30,
    language: str = TraceLanguage.PYTHON.value,
    expected_failure: bool = False,
    expected_exception_type: str | None = None,
    max_raw_trace_bytes: int = 1_000_000,
    max_compressed_events: int = 50,
    null_mode: bool = True,
    artifact_root: Path | None = None,
    artifact_store: ArtifactStore | None = None,
    repo_id: str | None = None,
    graph: object | None = None,
    snapshot_id: str | None = None,
    pre_raw_artefact: RawTraceArtefact | None = None,
    summarizer: TraceSummarizerInterface | None = None,
    registry: TraceAdapterRegistry | None = None,
) -> TraceCaptureOutput:
    trace_run_id = f"trace:{uuid.uuid4().hex}"
    contract_id = f"trace-contract:{uuid.uuid4().hex}"
    root = (
        Path(working_dir).expanduser().resolve()
        if working_dir
        else Path(script).expanduser().resolve().parent
    )
    artifacts_root = artifact_root or (root / ".llm-sca-artifacts")
    hcs = _hcs(trace_run_id, null_mode=null_mode)
    parsed_scope = _scope(scope_filter, suspects, changed_symbols, script, root)
    if parsed_scope.is_empty:
        return _terminal_output(
            trace_run_id=trace_run_id,
            contract_id=contract_id,
            language=language,
            adapter_id="unresolved",
            status=TraceRunStatus.SCOPE_EMPTY,
            hcs=hcs,
            diagnostics=[{"code": "scope_empty"}],
        )
    try:
        command_path = validate_command_allowlist(
            command=script,
            working_dir=root,
            allowed_roots=allowed_roots or [root],
        )
    except ValueError as exc:
        return _terminal_output(
            trace_run_id=trace_run_id,
            contract_id=contract_id,
            language=language,
            adapter_id="unresolved",
            status=TraceRunStatus.OUT_OF_SCOPE,
            hcs=hcs,
            diagnostics=[{"code": "out_of_scope", "message": str(exc)}],
        )
    language_value = TraceLanguage(language)
    adapter = (registry or TraceAdapterRegistry()).get(language_value.value)
    contract = TraceRunContract(
        contract_id=contract_id,
        command=str(command_path),
        args=args or [],
        timeout_seconds=timeout_seconds,
        environment_snapshot=build_environment_snapshot(root),
        working_dir=str(root),
        scope_filter=parsed_scope,
        redaction_policy={"status": "redacted", "exception_messages": "redacted"},
        max_raw_trace_bytes=max_raw_trace_bytes,
        max_compressed_events=max_compressed_events,
        language=language_value,
        adapter_id=adapter.adapter_id,
        expected_failure=expected_failure,
        expected_exception_type=expected_exception_type,
    )
    capture = await adapter.capture(
        trace_run_id=trace_run_id,
        contract=contract,
        artifact_root=artifacts_root,
    )
    artifact_refs: list[ArtifactRef] = []
    compressed: CompressedTrace | None = None
    raw_ref: ArtifactRef | None = None
    compressed_ref: ArtifactRef | None = None
    raw = capture.raw_artefact
    if raw is not None:
        raw_path = Path(raw.events_jsonl_path)
        raw_ref = artifact_ref_for_path(
            artifact_id=raw.artefact_id,
            path=raw_path,
            kind=ArtifactKind.TRACE,
            media_type="application/jsonl",
        )
        raw_ref = record_artifact(
            artifact_store,
            raw_ref,
            repo_id=repo_id,
            run_id=trace_run_id,
            payload_path=raw_path,
        )
        artifact_refs.append(raw_ref)
        raw_meta_path = trace_run_dir(artifacts_root, trace_run_id) / "raw_trace.json"
        write_model_json(raw_meta_path, raw)
        if capture.status not in {
            TraceRunStatus.TIMEOUT,
            TraceRunStatus.OUT_OF_SCOPE,
            TraceRunStatus.NOT_IMPLEMENTED,
        }:
            compressed = await (summarizer or NullTraceSummarizer()).summarize(
                raw,
                parsed_scope,
                budget_tokens=4_000,
            )
            if pre_raw_artefact is not None:
                state_diffs, divergence_points = compare_trace_events(
                    trace_run_id=trace_run_id,
                    pre_events=load_trace_events(pre_raw_artefact.events_jsonl_path),
                    post_events=load_trace_events(raw.events_jsonl_path),
                )
                divergence_points = bind_divergence_points(
                    divergence_points,
                    graph=graph,  # type: ignore[arg-type]
                    repo_id=repo_id,
                    snapshot_id=snapshot_id,
                )
                compressed = compressed.model_copy(
                    update={
                        "state_diffs": state_diffs,
                        "divergence_points": divergence_points,
                    }
                )
            compressed_path = (
                trace_run_dir(artifacts_root, trace_run_id) / "compressed_trace.json"
            )
            write_model_json(compressed_path, compressed)
            compressed_ref = artifact_ref_for_path(
                artifact_id=f"trace-compressed:{trace_run_id}",
                path=compressed_path,
                kind=ArtifactKind.SUMMARY,
                media_type="application/json",
            )
            compressed_ref = record_artifact(
                artifact_store,
                compressed_ref,
                repo_id=repo_id,
                run_id=trace_run_id,
                payload_path=compressed_path,
            )
            artifact_refs.append(compressed_ref)

    result = TraceRunResult(
        trace_run_id=trace_run_id,
        contract_id=contract.contract_id,
        language=contract.language,
        adapter_id=adapter.adapter_id,
        status=capture.status,
        raw_artefact_ref=raw_ref.artifact_id if raw_ref else None,
        compressed_trace_ref=compressed_ref.artifact_id if compressed_ref else None,
        state_diffs=compressed.state_diffs if compressed else [],
        divergence_points=compressed.divergence_points if compressed else [],
        non_reproducing=capture.non_reproducing,
        harness_condition_id=hcs.hcs_id,
        run_id=trace_run_id,
        wall_ms=capture.wall_ms,
        diagnostics=capture.diagnostics,
    )
    return TraceCaptureOutput(
        result=result,
        compressed_trace=compressed,
        raw_artefact=raw,
        harness_condition=hcs,
        artifact_refs=artifact_refs,
    )


def _scope(
    scope_filter: ScopeFilter | JsonObject | None,
    suspects: list[str] | None,
    changed_symbols: list[str] | None,
    script: str,
    root: Path,
) -> ScopeFilter:
    if scope_filter is not None:
        return ScopeFilter.model_validate(scope_filter)
    script_path = Path(script).expanduser().resolve()
    try:
        default_file = script_path.relative_to(root).as_posix()
    except ValueError:
        default_file = script_path.name
    return derive_scope_filter(
        suspects=suspects,
        changed_symbols=changed_symbols,
        default_file=default_file,
    )


def _hcs(trace_run_id: str, *, null_mode: bool) -> HarnessConditionSheet:
    return default_harness_condition_sheet(
        run_id=trace_run_id,
        model_backend="null-trace-summarizer" if null_mode else "trace-summarizer",
        tool_set=["capture_trace"],
        permission_mode="execute",
        verification_gates=["trace-contract", "redaction", "artifact-store"],
    )


def _terminal_output(
    *,
    trace_run_id: str,
    contract_id: str,
    language: str,
    adapter_id: str,
    status: TraceRunStatus,
    hcs: HarnessConditionSheet,
    diagnostics: list[JsonObject],
) -> TraceCaptureOutput:
    result = TraceRunResult(
        trace_run_id=trace_run_id,
        contract_id=contract_id,
        language=TraceLanguage(language),
        adapter_id=adapter_id,
        status=status,
        harness_condition_id=hcs.hcs_id,
        run_id=trace_run_id,
        diagnostics=diagnostics,
    )
    return TraceCaptureOutput(result=result, harness_condition=hcs)
