"""Execution-free certificate builder."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    ExecutionFreeCertificate,
)


def build_certificate(
    patch: CandidatePatch,
    *,
    conclusion: str = "partially_supported",
) -> ExecutionFreeCertificate:
    return ExecutionFreeCertificate(
        run_id=patch.run_id,
        candidate_index=patch.candidate_index,
        definitions=["target function", "changed symbols"],
        premises=[
            "patch addresses the symbol identified in fault localisation",
            "no new graph edges are removed by the patch",
        ],
        path_claims=["execution path through changed symbol satisfies postconditions"],
        counterexample_search="not_run",
        conclusion=conclusion,
        evidence_refs=[f"graph://slice/{patch.run_id}"],
        confidence="heuristic",
        unsupported_claims=(
            [] if conclusion == "supported" else ["dynamic-path coverage unverified"]
        ),
    )
