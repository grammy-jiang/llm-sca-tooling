"""Remaining-risk note generation."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import (
    BuildTestResult,
    PredicateMetadata,
    RemainingRiskNote,
    RiskLevel,
    SARIFDeltaVerificationResult,
)

_VULN_FAMILIES = {"injection", "xss", "ssrf", "deserialisation", "auth-bypass"}
_VULN_SEVERITIES = {"critical", "high"}


def is_vulnerability_class(metadata: PredicateMetadata) -> bool:
    if metadata.rule_family in _VULN_FAMILIES:
        return True
    if metadata.severity and metadata.severity.lower() in _VULN_SEVERITIES:
        return True
    return False


def generate_remaining_risk(
    *,
    alert_id: str,
    metadata: PredicateMetadata,
    sarif_delta: SARIFDeltaVerificationResult,
    build_test: BuildTestResult | None,
    poc_plus_available: bool = False,
    graph_dataflow_complete: bool = False,
) -> list[RemainingRiskNote]:
    """Produce a list of :class:`RemainingRiskNote` instances.

    Notes are required when:

    - The repair fixes a vulnerability-class alert without PoC+ tests.
    - Graph dataflow coverage of the repaired path is partial.
    - The only verification is that the SARIF alert disappeared.
    """
    notes: list[RemainingRiskNote] = []
    verification: list[str] = []
    if sarif_delta.original_alert_gone:
        verification.append("sarif_delta")
    if build_test and build_test.test_run_status == "passed":
        verification.append("test_run_pass")
    if poc_plus_available:
        verification.append("poc_plus")

    vuln = is_vulnerability_class(metadata)

    if vuln and not poc_plus_available:
        notes.append(
            RemainingRiskNote(
                alert_id=alert_id,
                risk_level=RiskLevel.HIGH,
                risk_description=(
                    "Vulnerability-class alert repaired without PoC+ confirmation."
                ),
                verification_method_used=verification,
                unverified_paths=["root_cause_behaviour"],
                recommended_followup=[
                    "author_poc_plus_test",
                    "manual_security_review",
                ],
            )
        )

    if not graph_dataflow_complete:
        notes.append(
            RemainingRiskNote(
                alert_id=alert_id,
                risk_level=RiskLevel.MEDIUM if vuln else RiskLevel.LOW,
                risk_description=(
                    "Graph dataflow evidence for the repaired path is partial."
                ),
                verification_method_used=verification,
                unverified_paths=["dataflow_completeness"],
                recommended_followup=["expand_graph_snapshot", "trace_capture"],
            )
        )

    if (
        not (build_test and build_test.test_run_status == "passed")
        and sarif_delta.original_alert_gone
    ):
        notes.append(
            RemainingRiskNote(
                alert_id=alert_id,
                risk_level=RiskLevel.MEDIUM,
                risk_description=(
                    "Only SARIF disappearance was verified; tests did not pass."
                ),
                verification_method_used=verification,
                unverified_paths=["test_pass"],
                recommended_followup=["run_full_test_suite"],
            )
        )

    if not notes:
        notes.append(
            RemainingRiskNote(
                alert_id=alert_id,
                risk_level=RiskLevel.NONE,
                risk_description="Full verification passed; no remaining risk identified.",
                verification_method_used=verification,
                unverified_paths=[],
                recommended_followup=[],
            )
        )
    return notes


__all__ = ["generate_remaining_risk", "is_vulnerability_class"]
