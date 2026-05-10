"""T2 regression runner skeleton."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import EvalRun, EvalStatus, utc_now_ts


def not_implemented_t2_run(eval_run: EvalRun) -> EvalRun:
    return eval_run.model_copy(
        update={
            "status": EvalStatus.PARTIAL,
            "end_ts": utc_now_ts(),
            "notes": [
                *eval_run.notes,
                "T2 regression runner skeleton only in Phase 10.",
            ],
        }
    )
