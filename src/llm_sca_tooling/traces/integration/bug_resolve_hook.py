"""Bug-resolve dynamic trace gate predicates."""

from __future__ import annotations


def should_run_trace_gate(
    *,
    static_gates_passed: bool,
    certificate_conclusion: str,
    reproduction_script: str | None,
    allow_dynamic_trace: bool,
) -> bool:
    return (
        allow_dynamic_trace
        and static_gates_passed
        and bool(reproduction_script)
        and certificate_conclusion in {"partially_supported", "unsupported"}
    )
