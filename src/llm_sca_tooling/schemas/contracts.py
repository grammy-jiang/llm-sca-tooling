"""Contract artefact models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from llm_sca_tooling.schemas.base import StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, Status
from llm_sca_tooling.schemas.graph import GraphDiagnostic
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, SourceSpan


class ContractArtifactType(StrEnum):
    JML = "jml"
    CODEQL = "codeql"
    SEMGREP = "semgrep"
    PYTEST = "pytest"
    UNIT_TEST = "unit_test"
    NATURAL_LANGUAGE_PROBE = "natural_language_probe"


class ContractArtifact(StrictBaseModel):
    artifact_id: str = id_field("Contract artefact identifier.")
    clause_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    artifact_type: ContractArtifactType
    target_symbols: list[str]
    source_clause_span: SourceSpan | None = None
    compile_status: Status
    last_run_status: Status
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    artifact_ref: ArtifactRef | None = None
    diagnostics: list[GraphDiagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract_evidence(self) -> ContractArtifact:
        if self.artifact_type == ContractArtifactType.NATURAL_LANGUAGE_PROBE:
            if self.provenance.evidence_strength != EvidenceStrength.SOFT_LLM:
                raise ValueError(
                    "natural language probes are soft evidence until verified"
                )
        if (
            self.provenance.derivation == DerivationType.LLM
            and self.compile_status == Status.PASSED
        ):
            if self.last_run_status != Status.PASSED:
                raise ValueError(
                    "LLM-derived contract artefacts require passing run status before promotion"
                )
        return self
