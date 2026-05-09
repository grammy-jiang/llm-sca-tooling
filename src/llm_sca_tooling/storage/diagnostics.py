"""Storage diagnostic result models."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class StorageDiagnostic(StrictBaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = "warning"
    details: JsonObject = Field(default_factory=dict)
