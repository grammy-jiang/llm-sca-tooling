"""Privacy redaction pipeline.

Applies secret scanning and PII detection to records before persistence.
Wraps the ``TraceRedactionAuditor`` patterns and adds write-time enforcement.
"""

from __future__ import annotations

import re
from typing import Any

from llm_sca_tooling.privacy.retention_policy import RetentionPolicy
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["PrivacyRedactionPipeline"]

logger = get_logger(__name__)

_REDACTED = "[REDACTED]"

# Patterns for write-time secret detection
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?i)(password|passwd|secret|token|api[_\-]?key|private[_\-]?key"
        r"|access[_\-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9+/=_\-]{8,})['\"]?"
    ),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9\-._~+/]+=*)"),
    re.compile(r"(ghp_[A-Za-z0-9]{36})"),
    re.compile(r"(sk-[A-Za-z0-9]{32,})"),
]

_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # email
]


class PrivacyRedactionPipeline:
    """Apply secret and PII redaction before any record is persisted.

    Args:
        policy: The workspace ``RetentionPolicy``.
    """

    def __init__(self, policy: RetentionPolicy) -> None:
        self._policy = policy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of *record* with secrets and PII redacted."""
        return self._redact_dict(record)  # type: ignore[no-any-return]

    def reject_if_secret(self, record: dict[str, Any]) -> None:
        """Raise ``ValueError`` if *record* contains an unredacted secret."""
        if not self._policy.secret_scan_enabled:
            return
        findings = self._find_secrets(record)
        if findings:
            raise ValueError(
                f"Record contains unredacted secret(s) in fields: "
                f"{', '.join(findings)}"
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redact_dict(self, obj: Any) -> Any:  # noqa: ANN401
        if isinstance(obj, dict):
            return {k: self._redact_dict(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._redact_dict(item) for item in obj]
        if isinstance(obj, str):
            return self._redact_str(obj)
        return obj

    def _redact_str(self, value: str) -> str:
        if self._policy.secret_scan_enabled:
            for pattern in _SECRET_PATTERNS:
                value = pattern.sub(_REDACTED, value)
        if self._policy.pii_detection_enabled:
            for pattern in _PII_PATTERNS:
                value = pattern.sub(_REDACTED, value)
        # Apply custom field rules (by value match)
        for field_pattern, replacement in self._policy.redaction_rules.items():
            value = re.sub(field_pattern, replacement, value)
        return value

    def _find_secrets(self, obj: Any, path: str = "") -> list[str]:  # noqa: ANN401
        found: list[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(self._find_secrets(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                found.extend(self._find_secrets(item, f"{path}[{i}]"))
        elif isinstance(obj, str):
            for pattern in _SECRET_PATTERNS:
                if pattern.search(obj):
                    found.append(path)
                    break
        return found
