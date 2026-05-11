"""Pre/postcondition draft generator."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    PrePostConditionDraft,
)


def draft_preconditions(patch: CandidatePatch) -> PrePostConditionDraft:
    primary = patch.changed_files[0] if patch.changed_files else "unknown"
    return PrePostConditionDraft(
        run_id=patch.run_id,
        candidate_index=patch.candidate_index,
        function_path=primary,
        preconditions=["input is not None", "state is initialised"],
        postconditions=["return value satisfies type contract", "no exception raised"],
        generation_method="null",
        confidence="unknown",
    )
