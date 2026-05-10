"""Memory write-path redaction and secret scanning."""

from __future__ import annotations

import re
from typing import Any

SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|credential)\s*[:=]\s*['\"]?[^'\"\s]+"
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def contains_secret(value: object) -> bool:
    return any(SECRET_RE.search(item) for item in _strings(value))


def scrub_pii(value: object) -> object:
    if isinstance(value, str):
        return EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    if isinstance(value, list):
        return [scrub_pii(item) for item in value]
    if isinstance(value, dict):
        return {str(key): scrub_pii(item) for key, item in value.items()}
    return value


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(_strings(str(key)))
            strings.extend(_strings(item))
        return strings
    if isinstance(value, list | tuple | set):
        strings = []
        for item in value:
            strings.extend(_strings(item))
        return strings
    return []


def jsonable(value: Any) -> Any:
    return scrub_pii(value)
