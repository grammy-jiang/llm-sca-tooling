"""Shared schema primitives and canonical serialization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"

JsonValue: TypeAlias = Any
JsonObject: TypeAlias = dict[str, Any]

NonEmptyString = str
Confidence = float


class StrictBaseModel(BaseModel):
    """Contract base model: forbid unknown top-level fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def canonical_json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Serialize a model or JSON-compatible value deterministically."""

    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def parse_utc_ts(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp must be non-empty")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_non_empty(value: str, field_name: str = "value") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def validate_confidence(value: float) -> float:
    if value < 0.0 or value > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return value


def validate_repo_relative_path(value: str) -> str:
    validate_non_empty(value, "path")
    if value.startswith("/") or "\\" in value:
        raise ValueError("path must be POSIX-style and repo-relative")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must not contain empty, current, or parent segments")
    return value


def ordered_ts(start_ts: str, end_ts: str | None) -> bool:
    return end_ts is None or parse_utc_ts(end_ts) >= parse_utc_ts(start_ts)


def schema_extra(schema_family: str, title: str, description: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://schemas.llm-sca.local/{schema_family}.schema.json",
        "title": title,
        "description": description,
        "schema_family": schema_family,
        "schema_version": SCHEMA_VERSION,
    }


StringId = str


def id_field(description: str) -> Any:
    return Field(min_length=1, description=description)
