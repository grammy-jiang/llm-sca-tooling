from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.dynamic_verdict import (
    run_dynamic_verdict_hook,
)
from llm_sca_tooling.workflows.impl_check.models import VerdictValue


def test_hook_dormant_without_phase16() -> None:
    c = extract_clauses("doc:d", "The system must work.\n")[0]
    record = run_dynamic_verdict_hook(c)
    assert record.available is False
    assert record.verdict is VerdictValue.UNKNOWN


def test_stage_is_6b() -> None:
    c = extract_clauses("doc:d", "must work.\n")[0]
    record = run_dynamic_verdict_hook(c)
    assert record.stage == "6b"


def test_with_dummy_capture_fn_still_unknown() -> None:
    c = extract_clauses("doc:d", "must work.\n")[0]
    record = run_dynamic_verdict_hook(c, trace_capture_fn=lambda _c: None)
    assert record.verdict is VerdictValue.UNKNOWN
