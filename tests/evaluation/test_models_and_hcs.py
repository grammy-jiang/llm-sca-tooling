from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.evaluation.harness_condition import (
    default_harness_condition_sheet,
    diff_harness_condition_sheets,
    render_compact_hcs,
    render_key_value_hcs,
)
from llm_sca_tooling.evaluation.models import EvalRun
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.t1_runner import T1SmokeRunner


def test_eval_run_round_trips_through_json() -> None:
    run = T1SmokeRunner(LocalSmokeAdapter()).run()
    payload = run.model_dump_json()
    restored = EvalRun.model_validate_json(payload)
    assert restored.eval_run_id == run.eval_run_id
    assert restored.instance_count == 5
    assert restored.harness_condition_id
    assert restored.contamination_canary_result.canary_verdict == "unknown"


def test_eval_run_missing_required_fields_fails_validation() -> None:
    with pytest.raises(ValidationError):
        EvalRun.model_validate({"suite_id": "local-smoke"})


def test_eval_run_id_is_high_entropy() -> None:
    ids = {
        T1SmokeRunner(LocalSmokeAdapter()).run(instance_ids=[]).eval_run_id
        for _ in range(5)
    }
    assert len(ids) == 5
    assert all(item.startswith("eval:") and len(item) > 20 for item in ids)


def test_harness_condition_render_and_diff_are_stable() -> None:
    sheet = default_harness_condition_sheet(
        run_id="eval:test",
        model_backend="null",
        tool_set=["run_eval_suite", "record_eval_result"],
        permission_mode="scoped-execute",
    )
    compact = render_compact_hcs(sheet)
    assert "model=null" in compact
    assert render_key_value_hcs(sheet) == render_key_value_hcs(sheet)
    changed = sheet.model_copy(update={"model_version": "null-v2"})
    diff = diff_harness_condition_sheets(sheet, changed)
    assert diff["model_version"]["after"] == "null-v2"
