"""capture_trace orchestration service."""

from __future__ import annotations

import uuid
from pathlib import Path

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.traces.adapters.registry import build_default_registry
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.compression.state_diff import (
    compute_divergence_points,
    compute_state_diffs,
)
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
    TraceRunContract,
    TraceRunResult,
)
from llm_sca_tooling.traces.scope_filter import (
    derive_scope_from_suspects,
    validate_scope,
)

_REGISTRY = build_default_registry()
_SUMMARIZER = NullTraceSummarizer()


async def capture_trace(
    *,
    script: str,
    args: list[str] | None = None,
    scope_filter: ScopeFilter | None = None,
    suspects: list[str] | None = None,
    timeout_seconds: int = 30,
    language: str = "python",
    pre_fix_artefact: RawTraceArtefact | None = None,
    workspace_root: Path | None = None,
    run_id: str | None = None,
    null_mode: bool = False,
) -> tuple[TraceRunResult, CompressedTrace | None]:
    run_id = run_id or f"trace:{uuid.uuid4().hex[:8]}"
    hcs = HarnessConditionSheet.create(run_id=run_id)

    # Derive scope
    effective_scope = scope_filter or derive_scope_from_suspects(suspects or [script])
    scope_diagnostics = validate_scope(effective_scope)

    contract = TraceRunContract(
        contract_id=f"contract:{run_id}",
        command=script,
        args=args or [],
        timeout_seconds=timeout_seconds,
        scope_filter=effective_scope,
        language=language,
        adapter_id=language,
    )

    if "scope_empty" in scope_diagnostics:
        return (
            TraceRunResult(
                trace_run_id=run_id,
                contract_id=contract.contract_id,
                language=language,
                adapter_id=language,
                status="scope_empty",
                harness_condition_id=hcs.hcs_id,
                run_id=run_id,
                diagnostics=scope_diagnostics,
            ),
            None,
        )

    # Validate path allowlist (HC2): command must be within workspace
    allowed_root = workspace_root or Path()
    script_path = Path(script)
    try:
        script_path.resolve().relative_to(allowed_root.resolve())
    except ValueError:
        if not null_mode and script_path.is_absolute():
            return (
                TraceRunResult(
                    trace_run_id=run_id,
                    contract_id=contract.contract_id,
                    language=language,
                    adapter_id=language,
                    status="out_of_scope",
                    harness_condition_id=hcs.hcs_id,
                    run_id=run_id,
                    diagnostics=["command_outside_path_allowlist"],
                ),
                None,
            )

    # Get adapter
    adapter = _REGISTRY.get(language)
    if adapter is None:
        return (
            TraceRunResult(
                trace_run_id=run_id,
                contract_id=contract.contract_id,
                language=language,
                adapter_id=language,
                status="not_implemented",
                harness_condition_id=hcs.hcs_id,
                run_id=run_id,
                diagnostics=[f"{language}_trace_adapter_not_available"],
            ),
            None,
        )

    if null_mode:
        from llm_sca_tooling.traces.artefact_store import write_artefact

        artefact = write_artefact(
            run_id, [], workspace_root=workspace_root, language=language
        )
        non_reproducing = False
    else:
        artefact, non_reproducing = await adapter.run(
            contract, workspace_root=workspace_root
        )

    compressed = _SUMMARIZER.summarize(artefact, effective_scope, budget_tokens=2000)

    # State diffs from two-trace comparison
    state_diffs = []
    divergence_points = []
    if pre_fix_artefact is not None:
        state_diffs = compute_state_diffs(pre_fix_artefact, artefact)
        divergence_points = compute_divergence_points(
            pre_fix_artefact, artefact, state_diffs
        )
        compressed = compressed.model_copy(
            update={
                "state_diffs": state_diffs,
                "divergence_points": divergence_points,
            }
        )

    status = "not_reproducing" if non_reproducing else "completed"
    if artefact.truncated:
        status = "truncated"

    return (
        TraceRunResult(
            trace_run_id=run_id,
            contract_id=contract.contract_id,
            language=language,
            adapter_id=language,
            status=status,
            raw_artefact_ref=artefact.artefact_id,
            compressed_trace_ref=f"compressed:{run_id}",
            state_diffs=state_diffs,
            divergence_points=divergence_points,
            non_reproducing=non_reproducing,
            harness_condition_id=hcs.hcs_id,
            run_id=run_id,
            diagnostics=[],
        ),
        compressed,
    )


def capture_trace_sync(
    *,
    script: str,
    suspects: list[str] | None = None,
    null_mode: bool = True,
    workspace_root: Path | None = None,
    run_id: str | None = None,
) -> tuple[TraceRunResult, CompressedTrace | None]:
    import asyncio

    return asyncio.run(
        capture_trace(
            script=script,
            suspects=suspects,
            null_mode=null_mode,
            workspace_root=workspace_root,
            run_id=run_id,
        )
    )
