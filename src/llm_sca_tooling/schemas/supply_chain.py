"""Supply-chain provenance contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel, id_field
from llm_sca_tooling.schemas.provenance import Provenance


class ComponentType(StrEnum):
    RUNTIME = "runtime"
    MCP_SERVER = "mcp_server"
    LANGUAGE_BACKEND = "language_backend"
    ANALYSER = "analyser"
    PROMPT_ASSET = "prompt_asset"
    SKILL = "skill"
    DEPENDENCY = "dependency"
    BENCHMARK = "benchmark"
    RULESET = "ruleset"


class SupplyChainRecord(StrictBaseModel):
    supply_chain_record_id: str = id_field("Supply-chain record identifier.")
    component_type: ComponentType
    name: str = Field(min_length=1)
    version: str | None = None
    source: str = Field(min_length=1)
    hash: str | None = None
    signature: str | None = None
    lockfile_ref: str | None = None
    license: str | None = None
    scanner_result_refs: list[str] = Field(default_factory=list)
    captured_ts: str = Field(min_length=1)
    provenance: Provenance
