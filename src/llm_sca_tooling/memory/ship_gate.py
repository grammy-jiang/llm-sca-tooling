"""Memory ship-gate evaluator."""

from __future__ import annotations

from llm_sca_tooling.evaluation.harness_condition import HarnessConditionSheet
from llm_sca_tooling.memory.models import MemoryShipGateResult

_REQUIRED_DELTA_PP = 3.0


def evaluate_ship_gate(
    eval_run_id: str,
    *,
    pass_rate_strategy: float = 0.0,
    pass_rate_baseline: float = 0.0,
    context_budget_used: int = 0,
) -> MemoryShipGateResult:
    """Evaluate whether HER+eviction beats success-only by >=3pp."""
    hcs = HarnessConditionSheet.create(run_id=eval_run_id)
    delta = pass_rate_strategy - pass_rate_baseline
    return MemoryShipGateResult(
        eval_run_id=eval_run_id,
        pass_rate_strategy=pass_rate_strategy,
        pass_rate_baseline=pass_rate_baseline,
        delta_pp=delta,
        gate_passed=delta >= _REQUIRED_DELTA_PP,
        context_budget_used=context_budget_used,
        harness_condition_id=hcs.hcs_id,
    )


def memory_weight(gate: MemoryShipGateResult) -> float:
    """Return 1.0 if gate passed (full weight), else 0.0 (stub weight)."""
    return 1.0 if gate.gate_passed else 0.0
