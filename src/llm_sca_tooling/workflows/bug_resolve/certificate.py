"""Execution-free certificate builder."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CertificateConclusion,
    ExecutionFreeCertificate,
)


def build_certificate(
    *,
    run_id: str,
    candidate_index: int,
    definitions: list[str] | None = None,
    premises: list[str] | None = None,
    path_claims: list[str] | None = None,
    counterexample_search: str = "",
    evidence_refs: list[str] | None = None,
    unsupported_claims: list[str] | None = None,
    confidence: float = 0.0,
    counterexample_found: bool = False,
) -> ExecutionFreeCertificate:
    """Build an :class:`ExecutionFreeCertificate` and decide its conclusion.

    Conclusion rules:
    - ``unsupported`` if a counterexample is found, or if explicit
      ``unsupported_claims`` are present and overlap with the premise set.
    - ``partially_supported`` if some premises are unverified
      (``unsupported_claims`` non-empty but premises remain).
    - ``supported`` if all premises are claimed and no unsupported claims.
    - ``unknown`` otherwise.
    """
    prem = list(premises or [])
    unsup = list(unsupported_claims or [])
    if counterexample_found:
        conclusion = CertificateConclusion.UNSUPPORTED
    elif not prem and not unsup:
        conclusion = CertificateConclusion.UNKNOWN
    elif unsup and prem:
        conclusion = CertificateConclusion.PARTIALLY_SUPPORTED
    elif unsup and not prem:
        conclusion = CertificateConclusion.UNSUPPORTED
    else:
        conclusion = CertificateConclusion.SUPPORTED
    return ExecutionFreeCertificate(
        run_id=run_id,
        candidate_index=candidate_index,
        definitions=list(definitions or []),
        premises=prem,
        path_claims=list(path_claims or []),
        counterexample_search=counterexample_search,
        conclusion=conclusion,
        evidence_refs=list(evidence_refs or []),
        confidence=max(0.0, min(1.0, confidence)),
        unsupported_claims=unsup,
    )


__all__ = ["build_certificate"]
