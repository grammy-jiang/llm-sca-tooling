"""Phase 15 blast-radius Pydantic v2 models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, id_field


class ImpactGroup(StrEnum):
    DIRECT_CALLERS = "direct_callers"
    DOWNSTREAM_BEHAVIOURS = "downstream_behaviours"
    TESTS = "tests"
    INTERFACES = "interfaces"
    SERVICES = "services"
    REPOSITORIES = "repositories"
    SARIF_REACHABILITY = "sarif_reachability"
    LINKED_DOCS_SPECS = "linked_docs_specs"


class MatchMethod(StrEnum):
    URL_PATTERN_MATCH = "url_pattern_match"
    NAME_HEURISTIC = "name_heuristic"
    CANDIDATE_EDGE = "candidate_edge"
    CROSS_REPO_UNRESOLVED = "cross_repo_unresolved"


class ABIChangeType(StrEnum):
    SIGNATURE_CHANGED = "signature_changed"
    VTABLE_AFFECTED = "vtable_affected"
    TEMPLATE_INSTANTIATION = "template_instantiation"
    OWNERSHIP_CHANGED = "ownership_changed"
    NULLNESS_CHANGED = "nullness_changed"
    NO_ABI_IMPACT = "no_abi_impact"
    UNKNOWN = "unknown"


class GeneratedStubImpactType(StrEnum):
    SOURCE_CONTRACT_CHANGED = "source_contract_changed"
    GENERATED_FILE_DIRECTLY_CHANGED = "generated_file_directly_changed"
    DOWNSTREAM_CONSUMER_OF_GENERATED = "downstream_consumer_of_generated"


class BlastRadiusConfig(StrictBaseModel):
    analyser_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    max_hops_override: int | None = Field(default=None, ge=1)
    include_cross_language_override: bool | None = None
    include_cross_repo_override: bool | None = None
    include_test_nodes: bool = True
    include_sarif_reachability: bool = True
    include_doc_spec_links: bool = True
    hub_dampening_threshold: int = Field(default=100, ge=1)
    extra: JsonObject = Field(default_factory=dict)


class ImpactRecord(StrictBaseModel):
    group: ImpactGroup
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    path_from_changed_symbol: list[str] = Field(default_factory=list)
    hop_distance: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    confirmed: bool
    edge_types_used: list[str] = Field(default_factory=list)
    change_type_relevance: str = Field(default="")
    breaking_change_flag: bool = False
    notes: str = Field(default="")


class GeneratedStubImpactNote(StrictBaseModel):
    diff_id: str = Field(min_length=1)
    generated_file_path: str = Field(min_length=1)
    generator_source: str = Field(default="")
    source_contract_node_id: str | None = None
    impact_type: GeneratedStubImpactType
    manual_edit_policy_flag: bool = False
    recommended_action: str = Field(default="")


class ABIImpactNote(StrictBaseModel):
    symbol_node_id: str = Field(min_length=1)
    symbol_path: str = Field(min_length=1)
    abi_change_type: ABIChangeType
    affected_template_instantiations: list[str] = Field(default_factory=list)
    ownership_edge_changes: list[str] = Field(default_factory=list)
    nullness_edge_changes: list[str] = Field(default_factory=list)
    build_target_reachability: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    diagnostics: list[str] = Field(default_factory=list)


class CrossRepoImpactRecord(StrictBaseModel):
    repo_id: str = Field(min_length=1)
    consuming_node_ids: list[str] = Field(default_factory=list)
    hop_distance: int = Field(ge=0)
    is_partial: bool = False
    partial_reason: str = Field(default="")
    confidence: float = Field(ge=0.0, le=1.0)


class AmbiguousLinkRecord(StrictBaseModel):
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    match_method: MatchMethod
    reason_ambiguous: str = Field(default="")
    recommended_followup: str = Field(default="")


class BlastRadiusReport(StrictBaseModel):
    report_id: str = id_field("Blast-radius report identifier.")
    diff_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    traversal_policy_ref: str = Field(default="")
    impact_groups: dict[str, list[Any]] = Field(default_factory=dict)
    confirmed_impact_count: int = Field(default=0, ge=0)
    ambiguous_impact_count: int = Field(default=0, ge=0)
    generated_stub_notes: list[GeneratedStubImpactNote] = Field(default_factory=list)
    abi_impact_notes: list[ABIImpactNote] = Field(default_factory=list)
    cross_repo_impact_records: list[CrossRepoImpactRecord] = Field(default_factory=list)
    ambiguous_links: list[AmbiguousLinkRecord] = Field(default_factory=list)
    is_partial: bool = False
    partial_reason: str = Field(default="")
    sarif_reachability_summary: str = Field(default="")
    linked_docs_summary: str = Field(default="")
    human_readable_summary: str = Field(default="")
    created_ts: str = Field(min_length=1)

    @staticmethod
    def _now_ts() -> str:
        return datetime.now(UTC).isoformat()


__all__ = [
    "ABIChangeType",
    "ABIImpactNote",
    "AmbiguousLinkRecord",
    "BlastRadiusConfig",
    "BlastRadiusReport",
    "CrossRepoImpactRecord",
    "GeneratedStubImpactNote",
    "GeneratedStubImpactType",
    "ImpactGroup",
    "ImpactRecord",
    "MatchMethod",
]
