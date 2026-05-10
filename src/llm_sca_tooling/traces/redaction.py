"""Trace redaction helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from llm_sca_tooling.schemas.base import JsonObject

SECRET_NAME_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|credential)", re.I
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"
)


def stable_hash(value: object, *, length: int = 16) -> str:
    payload = repr(value).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:length]


def redaction_policy_hash(policy: JsonObject) -> str:
    payload = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def environment_snapshot_hash(snapshot: JsonObject) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def redact_string(value: str) -> tuple[str, bool]:
    if SECRET_VALUE_RE.search(value):
        return SECRET_VALUE_RE.sub("[REDACTED]", value), True
    return value, False


def redacted_type_hint(name: str, value: Any) -> str:
    if SECRET_NAME_RE.search(name):
        return "[REDACTED]"
    type_name = type(value).__name__
    return f"{type_name}:sha256:{stable_hash(value)}"


def redacted_return_type_hash(value: Any) -> str:
    return f"{type(value).__name__}:sha256:{stable_hash(value)}"
