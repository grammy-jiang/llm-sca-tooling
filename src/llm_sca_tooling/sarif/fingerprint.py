"""Stable alert fingerprinting."""

from __future__ import annotations

import hashlib
import re

from llm_sca_tooling.sarif.models import NormalizedSeverity


def normalize_message(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compute_alert_fingerprint(
    *,
    analyser_id: str,
    rule_id: str,
    file_path: str | None,
    message: str,
    snippet: str | None = None,
) -> str:
    canonical = "\n".join([analyser_id, rule_id, file_path or "", normalize_message(message), normalize_message(snippet or "")])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def compute_partial_fingerprint(
    *,
    rule_family: str,
    normalized_severity: NormalizedSeverity,
    start_column: int | None,
) -> str:
    canonical = "\n".join([rule_family, normalized_severity.value, str(start_column or "")])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]

