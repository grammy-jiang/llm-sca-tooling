"""Harness Condition Sheet schema model.

Every benchmark report, workflow run, release gate, and operational review
should include a HarnessCondition.  A workflow run without a harness
condition is operationally incomplete.
"""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.governance import ToolPermission
from llm_sca_tooling.schemas.operations import GateStatus, GateType
from llm_sca_tooling.schemas.provenance import Provenance
from llm_sca_tooling.schemas.run_records import ContextBudget, RedactionPolicy

__all__ = [
    "RuntimeRef",
    "ModelBackendRef",
    "ManifestHash",
    "SandboxDescriptor",
    "RetryPolicy",
    "VerificationGate",
    "HarnessCondition",
]


class RuntimeRef(StrictModel):
    name: NonEmptyStr
    version: str | None = None


class ModelBackendRef(StrictModel):
    name: NonEmptyStr
    version: str | None = None
    api_version: str | None = None


class ManifestHash(StrictModel):
    manifest_path: NonEmptyStr
    git_sha: str | None = None
    content_hash: str | None = None


class SandboxDescriptor(StrictModel):
    sandbox_type: str = "none"
    devcontainer_sha: str | None = None
    notes: str | None = None


class RetryPolicy(StrictModel):
    max_retries: int = 3
    backoff_strategy: str = "none"


class VerificationGate(StrictModel):
    gate_name: NonEmptyStr
    gate_type: GateType
    enabled: bool = True
    status: GateStatus = GateStatus.unknown
    skip_reason: str | None = None


class HarnessCondition(StrictModel):
    schema_version: str = SCHEMA_VERSION
    harness_condition_id: NonEmptyStr
    run_id: str | None = None
    captured_ts: NonEmptyStr
    runtime: RuntimeRef
    model_backend: ModelBackendRef | None = None
    manifest_hashes: list[ManifestHash] = Field(default_factory=list)
    toolset_hash: str = "unknown"
    exposed_tools: list[ToolPermission] = Field(default_factory=list)
    permission_profile: str = "read-only"
    sandbox: SandboxDescriptor = SandboxDescriptor()
    network_policy: str = "deny-by-default"
    context_policy: ContextBudget = ContextBudget()
    retry_policy: RetryPolicy = RetryPolicy()
    verification_gates: list[VerificationGate] = Field(default_factory=list)
    telemetry_location: str | None = None
    redaction_policy: RedactionPolicy = RedactionPolicy()
    sampling_capability: str = "unknown"
    supply_chain_refs: list[str] = Field(default_factory=list)
    provenance: Provenance
