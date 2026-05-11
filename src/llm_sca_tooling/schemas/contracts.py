"""Contract artefact models.

Contract artefacts are produced by implementation-check, SAST repair, and
patch review.  They cannot become hard evidence until they compile, lint,
or pass their validation gate.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.graph import GraphDiagnostic
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, SourceSpan

__all__ = ["ArtifactType", "ArtifactRunStatus", "ContractArtifact"]


class ArtifactType(str, Enum):
    jml = "jml"
    codeql = "codeql"
    semgrep = "semgrep"
    pytest = "pytest"
    unit_test = "unit_test"
    natural_language_probe = "natural_language_probe"


class ArtifactRunStatus(str, Enum):
    not_run = "not_run"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    unknown = "unknown"


class ContractArtifact(StrictModel):
    artifact_id: NonEmptyStr
    clause_id: NonEmptyStr
    language: NonEmptyStr
    artifact_type: ArtifactType
    target_symbols: list[str] = Field(default_factory=list)
    source_clause_span: SourceSpan | None = None
    compile_status: ArtifactRunStatus = ArtifactRunStatus.not_run
    last_run_status: ArtifactRunStatus = ArtifactRunStatus.not_run
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    provenance: Provenance
    artifact_ref: ArtifactRef | None = None
    diagnostics: list[GraphDiagnostic] = Field(default_factory=list)
