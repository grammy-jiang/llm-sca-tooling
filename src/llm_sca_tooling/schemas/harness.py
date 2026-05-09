"""Harness Condition Sheet contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel, id_field
from llm_sca_tooling.schemas.governance import (
    ContextBudget,
    ManifestHash,
    ModelBackendRef,
    RedactionPolicy,
    RetryPolicy,
    RuntimeRef,
    SandboxDescriptor,
    ToolPermission,
    VerificationGate,
)
from llm_sca_tooling.schemas.provenance import Provenance


class SamplingCapability(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class HarnessCondition(StrictBaseModel):
    schema_family: Literal["harness-condition"] = "harness-condition"
    schema_version: str = SCHEMA_VERSION
    harness_condition_id: str = id_field("Harness condition identifier.")
    run_id: str | None = None
    captured_ts: str = Field(min_length=1)
    runtime: RuntimeRef
    model_backend: ModelBackendRef | None = None
    manifest_hashes: list[ManifestHash]
    toolset_hash: str = Field(min_length=1)
    exposed_tools: list[ToolPermission]
    permission_profile: str = Field(min_length=1)
    sandbox: SandboxDescriptor
    network_policy: str = Field(min_length=1)
    context_policy: ContextBudget
    retry_policy: RetryPolicy
    verification_gates: list[VerificationGate]
    telemetry_location: str = Field(min_length=1)
    redaction_policy: RedactionPolicy
    sampling_capability: SamplingCapability
    supply_chain_refs: list[str] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_required_sections(self) -> "HarnessCondition":
        if not self.manifest_hashes:
            raise ValueError("harness condition requires manifest hashes")
        if not self.exposed_tools:
            raise ValueError("harness condition requires exposed tool permissions")
        if not self.verification_gates:
            raise ValueError("harness condition requires verification gates")
        return self
