"""Phase 15 blast-radius models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.evaluation.models import now_ts


class StrictBRModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChangeType(str, Enum):
    internal_implementation = "INTERNAL_IMPLEMENTATION"
    public_api_change = "PUBLIC_API_CHANGE"
    idl_schema_contract_change = "IDL_SCHEMA_CONTRACT_CHANGE"
    security_sensitive_change = "SECURITY_SENSITIVE_CHANGE"
    generated_file_change = "GENERATED_FILE_CHANGE"
    mixed = "MIXED"
    unknown = "UNKNOWN"


class ImpactGroup(str, Enum):
    direct_callers = "DIRECT_CALLERS"
    downstream_behaviours = "DOWNSTREAM_BEHAVIOURS"
    tests = "TESTS"
    interfaces = "INTERFACES"
    services = "SERVICES"
    repositories = "REPOSITORIES"
    sarif_reachability = "SARIF_REACHABILITY"
    linked_docs_specs = "LINKED_DOCS_SPECS"


class BlastRadiusConfig(StrictBRModel):
    max_hops: int = 5
    confirmed_only: bool = False
    include_cross_language: bool = True
    include_cross_repo: bool = True
    include_generated_files: bool = True
    include_sarif_reachability: bool = True
    include_doc_spec_links: bool = True
    analyser_confidence_threshold: float = 0.7


class TraversalPolicy(StrictBRModel):
    change_type: ChangeType
    max_hops: int
    follow_edge_types: list[str] = Field(default_factory=list)
    stop_at_interface_boundary: bool = False
    include_cross_language: bool = False
    include_cross_repo: bool = False
    include_generated_files: bool = True
    include_test_nodes: bool = True
    include_sarif_reachability: bool = False
    include_doc_spec_links: bool = False
    depth_multiplier_security: float = 1.0
    confirmed_only: bool = False


class ImpactRecord(StrictBRModel):
    group: ImpactGroup
    node_id: str
    node_type: str = "symbol"
    path_from_changed_symbol: list[str] = Field(default_factory=list)
    hop_distance: int = 1
    confidence: str = "heuristic"
    confirmed: bool = True
    edge_types_used: list[str] = Field(default_factory=list)
    change_type_relevance: str = "direct"
    breaking_change_flag: bool = False
    notes: str = ""


class GeneratedStubImpactNote(StrictBRModel):
    diff_id: str
    generated_file_path: str
    generator_source: str
    source_contract_node_id: str
    impact_type: str
    manual_edit_policy_flag: bool = False
    recommended_action: str


class ABIImpactNote(StrictBRModel):
    symbol_node_id: str
    symbol_path: str
    abi_change_type: str
    affected_template_instantiations: list[str] = Field(default_factory=list)
    ownership_edge_changes: list[str] = Field(default_factory=list)
    nullness_edge_changes: list[str] = Field(default_factory=list)
    build_target_reachability: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    diagnostics: list[str] = Field(default_factory=list)


class CrossRepoImpactRecord(StrictBRModel):
    repo_id: str
    repo_path: str
    consuming_symbol_ids: list[str] = Field(default_factory=list)
    interface_type: str = "unknown"
    hop_distance: int = 1
    is_partial: bool = True
    diagnostics: list[str] = Field(default_factory=list)


class AmbiguousLinkRecord(StrictBRModel):
    source_node_id: str
    target_node_id: str
    edge_type: str
    confidence: float = 0.0
    match_method: str
    reason_ambiguous: str
    recommended_followup: str


class BlastRadiusReport(StrictBRModel):
    report_id: str
    diff_id: str
    run_id: str
    change_type: ChangeType
    traversal_policy_ref: str
    impact_groups: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    confirmed_impact_count: int = 0
    ambiguous_impact_count: int = 0
    generated_stub_notes: list[GeneratedStubImpactNote] = Field(default_factory=list)
    abi_impact_notes: list[ABIImpactNote] = Field(default_factory=list)
    cross_repo_impact_records: list[CrossRepoImpactRecord] = Field(default_factory=list)
    ambiguous_links: list[AmbiguousLinkRecord] = Field(default_factory=list)
    is_partial: bool = False
    partial_reason: str = ""
    sarif_reachability_summary: str = ""
    linked_docs_summary: str = ""
    human_readable_summary: str = ""
    created_ts: str = Field(default_factory=now_ts)
