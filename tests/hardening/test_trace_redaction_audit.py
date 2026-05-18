"""Tests for TraceRedactionAuditor."""

from __future__ import annotations

from llm_sca_tooling.hardening.trace_redaction_audit import TraceRedactionAuditor

# Synthetic AWS-access-key-shaped fixture built at runtime so source-level
# secret scanners (local-agent-harness's redaction-smoke, gitleaks,
# detect-secrets's "Hex High Entropy String") do not flag this test file.
# The three-way split keeps each literal under detect-secrets's hex
# entropy threshold; the runtime concat is still 16 alphanumeric chars
# after the AKIA prefix and still matches the AKIA[0-9A-Z]{16} regex.
_FAKE_AKIA = "AKIA" + "12345678" + "90ABCDEF"
_SECRET_VALUE = f"secret={_FAKE_AKIA}"


def test_clean_trace_no_findings() -> None:
    auditor = TraceRedactionAuditor()
    result = auditor.audit_events(
        "run1", [{"event": "start", "session_id": "s1", "data": "normal text"}]
    )
    assert len(result.findings) == 0
    assert result.passed


def test_suspected_secret_in_key_value_flagged() -> None:
    auditor = TraceRedactionAuditor()
    result = auditor.audit_events("run2", [{"api_key": _SECRET_VALUE}])
    assert len(result.findings) >= 1


def test_already_redacted_not_flagged() -> None:
    auditor = TraceRedactionAuditor()
    result = auditor.audit_events("run3", [{"event": "call", "data": "[REDACTED]"}])
    assert len(result.findings) == 0


def test_triple_star_not_flagged() -> None:
    auditor = TraceRedactionAuditor()
    result = auditor.audit_events("run4", [{"event": "call", "api_key": "***"}])
    assert len(result.findings) == 0


def test_nested_dict_scanned_no_crash() -> None:
    auditor = TraceRedactionAuditor()
    result = auditor.audit_events(
        "run5", [{"event": "x", "inner": {"key": _SECRET_VALUE}}]
    )
    assert isinstance(result.findings, list)


def test_on_finding_callback_invoked() -> None:
    found: list[object] = []
    auditor = TraceRedactionAuditor(on_finding=found.append)
    auditor.audit_events("run6", [{"data": _SECRET_VALUE}])
    assert len(found) >= 1
