"""Supply-chain provenance models."""

from __future__ import annotations

from enum import Enum

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import Provenance

__all__ = ["ComponentType", "SupplyChainRecord"]


class ComponentType(str, Enum):
    runtime = "runtime"
    mcp_server = "mcp_server"
    language_backend = "language_backend"
    analyser = "analyser"
    prompt_asset = "prompt_asset"
    skill = "skill"
    dependency = "dependency"
    benchmark = "benchmark"
    ruleset = "ruleset"


class SupplyChainRecord(StrictModel):
    supply_chain_record_id: NonEmptyStr
    component_type: ComponentType
    name: NonEmptyStr
    version: NonEmptyStr
    source: str | None = None
    hash: str | None = None
    signature: str | None = None
    lockfile_ref: str | None = None
    license: str | None = None
    scanner_result_refs: list[str] = []
    captured_ts: NonEmptyStr
    provenance: Provenance
