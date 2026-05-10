"""Memory ship-gate evaluator."""

from __future__ import annotations

from llm_sca_tooling.memory.models import MemoryShipGateResult


def evaluate_memory_ship_gate(
    *,
    eval_run_id: str,
    pass_rate_strategy: float,
    pass_rate_baseline: float,
    context_budget_used: int,
    harness_condition_id: str,
    strategy_tested: str = "her-plus-eviction",
    baseline_strategy: str = "success-only-memory",
) -> MemoryShipGateResult:
    delta_pp = (pass_rate_strategy - pass_rate_baseline) * 100.0
    gate_passed = delta_pp >= 3.0
    return MemoryShipGateResult(
        eval_run_id=eval_run_id,
        strategy_tested=strategy_tested,
        baseline_strategy=baseline_strategy,
        pass_rate_strategy=pass_rate_strategy,
        pass_rate_baseline=pass_rate_baseline,
        delta_pp=delta_pp,
        gate_passed=gate_passed,
        context_budget_used=context_budget_used,
        harness_condition_id=harness_condition_id,
        memory_hint_weight=1.0 if gate_passed else 0.0,
    )
