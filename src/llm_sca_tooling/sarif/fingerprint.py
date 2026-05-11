"""Stable SARIF alert fingerprinting."""

from __future__ import annotations

import hashlib
import re

__all__ = ["compute_alert_fingerprint", "compute_partial_fingerprint"]


def compute_alert_fingerprint(
    *,
    analyser_id: str,
    rule_id: str,
    file_path: str | None,
    start_line: int | None,
    message: str,
    snippet: str | None = None,
) -> str:
    payload = "|".join(
        [
            analyser_id,
            rule_id,
            file_path or "",
            str(start_line or ""),
            _normalize_text(message),
            _hash_snippet(snippet),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def compute_partial_fingerprint(
    *, rule_family: str, normalized_severity: str, start_column: int | None
) -> str:
    payload = f"{rule_family}|{normalized_severity}|{start_column or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _hash_snippet(snippet: str | None) -> str:
    if snippet is None:
        return ""
    return hashlib.sha256(_normalize_text(snippet).encode()).hexdigest()[:16]
