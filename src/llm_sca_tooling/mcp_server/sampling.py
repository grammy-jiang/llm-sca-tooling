"""Sampling capability detection."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class SamplingCapabilityRecord(StrictBaseModel):
    status: str
    details: JsonObject = Field(default_factory=dict)


def detect_sampling(enabled: bool, client_capabilities: JsonObject | None = None) -> SamplingCapabilityRecord:
    if not enabled:
        return SamplingCapabilityRecord(status="unsupported", details={"reason": "disabled_by_server_config"})
    if client_capabilities is None:
        return SamplingCapabilityRecord(status="unknown", details={})
    sampling = client_capabilities.get("sampling")
    return SamplingCapabilityRecord(status="supported" if sampling else "unsupported", details={"client_sampling": sampling})
