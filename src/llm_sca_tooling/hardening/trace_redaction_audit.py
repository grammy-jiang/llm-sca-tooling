"""Trace redaction audit."""

from __future__ import annotations

from llm_sca_tooling.hardening.models import TraceRedactionAuditResult
from llm_sca_tooling.privacy.redaction import contains_sensitive_value
from llm_sca_tooling.schemas.base import JsonObject


class TraceRedactionAuditor:
    def audit_events(self, events: list[JsonObject]) -> TraceRedactionAuditResult:
        findings = [
            {"event_id": event.get("event_id"), "code": "unredacted_secret"}
            for event in events
            if contains_sensitive_value(event)
        ]
        return TraceRedactionAuditResult(passed=not findings, findings=findings)
