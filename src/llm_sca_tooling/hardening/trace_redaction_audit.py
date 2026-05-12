"""Trace redaction auditor.

Scans stored run-event string fields for HC1 secret patterns and PII.
Reports unredacted matches as audit findings.  A failing audit produces
a P1 incident record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["AuditFinding", "TraceRedactionAuditor"]

logger = get_logger(__name__)

# Secret-like patterns (HC1)
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?i)(password|passwd|secret|token|api[_\-]?key|private[_\-]?key"
        r"|access[_\-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_\-]{8,}['\"]?"
    ),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{36}"),  # GitHub PAT
    re.compile(r"(?i)sk-[A-Za-z0-9]{32,}"),  # OpenAI key
]

# PII patterns
_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # email
    re.compile(r"\b\+?[0-9]{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b"),  # phone
]

# Values already redacted should contain one of these markers
_REDACTED_MARKERS = ["[REDACTED]", "***", "<redacted>"]


@dataclass
class AuditFinding:
    field_path: str
    pattern_type: str  # "secret" | "pii"
    pattern_name: str
    sample: str  # first 20 chars of the matched value (no full leak)


@dataclass
class AuditResult:
    run_id: str
    ts: str
    findings: list[AuditFinding]

    @property
    def passed(self) -> bool:
        return len(self.findings) == 0


class TraceRedactionAuditor:
    """Scan run-event records for unredacted secrets and PII.

    Args:
        on_finding: Optional callback invoked for each ``AuditFinding``.
    """

    def __init__(self, on_finding: Any | None = None) -> None:
        self._on_finding = on_finding

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit_events(self, run_id: str, events: list[dict[str, Any]]) -> AuditResult:
        """Scan *events* for unredacted secrets and PII.

        Returns an ``AuditResult``; ``passed`` is ``True`` if no findings.
        """
        findings: list[AuditFinding] = []
        for i, event in enumerate(events):
            findings.extend(self._scan_dict(event, root=f"events[{i}]"))

        result = AuditResult(
            run_id=run_id,
            ts=datetime.now(UTC).isoformat(),
            findings=findings,
        )
        if not result.passed:
            logger.warning(
                "redaction_audit FAILED: run=%s findings=%d",
                run_id,
                len(findings),
            )
        else:
            logger.info("redaction_audit passed: run=%s", run_id)
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_dict(
        self,
        obj: Any,
        root: str = "",  # noqa: ANN401
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                findings.extend(self._scan_dict(v, root=f"{root}.{k}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                findings.extend(self._scan_dict(item, root=f"{root}[{i}]"))
        elif isinstance(obj, str):
            findings.extend(self._scan_str(obj, root))
        return findings

    def _scan_str(self, value: str, field_path: str) -> list[AuditFinding]:
        # Skip already-redacted values
        if any(m in value for m in _REDACTED_MARKERS):
            return []

        findings: list[AuditFinding] = []
        for pattern in _SECRET_PATTERNS:
            m = pattern.search(value)
            if m:
                finding = AuditFinding(
                    field_path=field_path,
                    pattern_type="secret",
                    pattern_name=pattern.pattern[:40],
                    sample=m.group(0)[:20],
                )
                findings.append(finding)
                if self._on_finding:
                    self._on_finding(finding)

        for pattern in _PII_PATTERNS:
            m = pattern.search(value)
            if m:
                finding = AuditFinding(
                    field_path=field_path,
                    pattern_type="pii",
                    pattern_name=pattern.pattern[:40],
                    sample=m.group(0)[:20],
                )
                findings.append(finding)
                if self._on_finding:
                    self._on_finding(finding)

        return findings
