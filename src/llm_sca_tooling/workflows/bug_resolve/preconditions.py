"""Pre/postcondition draft generator."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import PrePostConditionDraft


def generate_prepost_draft(
    *,
    run_id: str,
    candidate_index: int,
    function_path: str,
    preconditions: list[str] | None = None,
    postconditions: list[str] | None = None,
    generation_method: str = "null-adapter",
    compile_status: str = "unknown",
) -> PrePostConditionDraft:
    """Construct a pre/postcondition draft.

    Pre/postconditions are emitted as supporting evidence; ``compile_status``
    of ``unknown`` is reported as the draft confidence so callers know the
    artefact has not been independently verified.
    """
    if not function_path.strip():
        raise ValueError("function_path must be non-empty")
    confidence = (
        "verified"
        if compile_status == "verified"
        else "supporting" if compile_status == "compiles" else "unknown"
    )
    return PrePostConditionDraft(
        run_id=run_id,
        candidate_index=candidate_index,
        function_path=function_path,
        preconditions=list(preconditions or []),
        postconditions=list(postconditions or []),
        generation_method=generation_method,
        confidence=confidence,
    )


__all__ = ["generate_prepost_draft"]
