"""Redaction helpers for exported ledgers and privacy audits."""

from __future__ import annotations

import re
from collections.abc import Iterable

SENSITIVE_KEY_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{12,}"),
    re.compile(r"pypi-[A-Za-z0-9_-]{20,}"),
)
REDACTION_TEXT = "[REDACTED]"


def redact_for_export(
    value: object, *, additional_sensitive_keys: Iterable[str] = ()
) -> object:
    """Return a JSON-compatible copy with likely secrets redacted."""

    key_parts = SENSITIVE_KEY_PARTS | {key.lower() for key in additional_sensitive_keys}
    return _redact(value, key_parts=key_parts)


def contains_sensitive_value(value: object) -> bool:
    """Detect likely unredacted sensitive text in a nested JSON-like value."""

    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                return True
            if contains_sensitive_value(child):
                return True
        return False
    if isinstance(value, list | tuple | set):
        return any(contains_sensitive_value(child) for child in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    return False


def _redact(value: object, *, key_parts: set[str]) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in key_parts):
                redacted[str(key)] = REDACTION_TEXT
            else:
                redacted[str(key)] = _redact(child, key_parts=key_parts)
        return redacted
    if isinstance(value, list | tuple | set):
        return [_redact(child, key_parts=key_parts) for child in value]
    if isinstance(value, str):
        text_value = value
        for pattern in SECRET_PATTERNS:
            text_value = pattern.sub(REDACTION_TEXT, text_value)
        return text_value
    return value
