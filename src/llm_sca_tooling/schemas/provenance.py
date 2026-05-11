"""Provenance, snapshot, span, and artefact models.

These primitives are required by every domain model.  A fact without
provenance fails validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import JsonValue, NonEmptyStr, StrictModel

__all__ = [
    "RedactionStatus",
    "EvidenceStrength",
    "DerivationType",
    "IndexStatus",
    "PolicyAction",
    "RepoRef",
    "SnapshotRef",
    "SourceSpan",
    "ArtifactRef",
    "ArtifactKind",
    "Provenance",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RedactionStatus(str, Enum):
    not_required = "not_required"
    redacted = "redacted"
    hash_only = "hash_only"
    blocked = "blocked"
    unknown = "unknown"


# Numeric strength ordering: hard_static(5) is strongest, soft_llm(1) is weakest.
# Defined at module level so Enum members can access it without `self` lookup quirks.
_EVIDENCE_NUMERIC: dict[str, int] = {
    "hard_static": 5,
    "hard_dynamic": 4,
    "structured_repository": 3,
    "calibrated_model": 2,
    "soft_llm": 1,
}


class EvidenceStrength(str, Enum):
    """Ordered from strongest to weakest.

    The numeric ordering supports comparisons:
    ``EvidenceStrength.hard_static > EvidenceStrength.soft_llm`` is True.
    ``min([hard_static, soft_llm])`` returns ``soft_llm``.
    """

    hard_static = "hard_static"
    hard_dynamic = "hard_dynamic"
    structured_repository = "structured_repository"
    calibrated_model = "calibrated_model"
    soft_llm = "soft_llm"

    @property
    def numeric(self) -> int:
        return _EVIDENCE_NUMERIC[self.value]

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, EvidenceStrength):
            return NotImplemented
        return self.numeric > other.numeric

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, EvidenceStrength):
            return NotImplemented
        return self.numeric < other.numeric

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, EvidenceStrength):
            return NotImplemented
        return self.numeric >= other.numeric

    def __le__(self, other: object) -> bool:
        if not isinstance(other, EvidenceStrength):
            return NotImplemented
        return self.numeric <= other.numeric


class DerivationType(str, Enum):
    parser = "parser"
    analyser = "analyser"
    build = "build"
    test = "test"
    trace = "trace"
    llm = "llm"
    heuristic = "heuristic"
    policy = "policy"
    review = "review"


class IndexStatus(str, Enum):
    fresh = "fresh"
    stale = "stale"
    partial = "partial"
    mixed = "mixed"
    unknown = "unknown"


class PolicyAction(str, Enum):
    allow = "allow"
    deny = "deny"
    approval_required = "approval_required"
    blocked = "blocked"
    checkpoint = "checkpoint"
    force_unknown = "force_unknown"
    not_applicable = "not_applicable"


class ArtifactKind(str, Enum):
    graph_chunk = "graph_chunk"
    sarif = "sarif"
    trace = "trace"
    diff = "diff"
    test_output = "test_output"
    log = "log"
    summary = "summary"
    report = "report"
    schema = "schema"
    other = "other"


# ---------------------------------------------------------------------------
# Primitive models
# ---------------------------------------------------------------------------


class RepoRef(StrictModel):
    """Stable reference to a repository."""

    repo_id: NonEmptyStr
    name: str | None = None
    root_ref: str | None = None
    remote_url_hash: str | None = None
    default_branch: str | None = None


class SnapshotRef(StrictModel):
    """Reference to a specific repository snapshot."""

    repo_id: NonEmptyStr
    git_sha: str | None = None
    branch: str | None = None
    worktree_snapshot_id: str | None = None
    dirty: bool = False
    index_status: IndexStatus = IndexStatus.unknown
    captured_ts: NonEmptyStr

    @field_validator("index_status", mode="before")
    @classmethod
    def _no_implicit_fresh(cls, v: object) -> object:
        """index_status must not default to 'fresh' when unknown."""
        return v


class SourceSpan(StrictModel):
    """Source location within a repository-relative file."""

    file_path: NonEmptyStr
    start_line: int = Field(ge=1)
    start_col: int | None = None
    end_line: int = Field(ge=1)
    end_col: int | None = None
    byte_start: int | None = None
    byte_end: int | None = None
    encoding: str | None = None

    @model_validator(mode="after")
    def _end_ge_start(self) -> SourceSpan:
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        return self


class ArtifactRef(StrictModel):
    """Reference to an external artefact (SARIF report, trace file, diff, etc.)."""

    artifact_id: NonEmptyStr
    kind: ArtifactKind
    uri: NonEmptyStr
    sha256: str | None = None
    size_bytes: int | None = None
    media_type: str | None = None
    redaction_status: RedactionStatus
    created_ts: str | None = None


class Provenance(StrictModel):
    """Evidence provenance — required on every durable fact.

    Every code-related fact must carry ``repo`` and ``snapshot``.
    LLM-derived evidence (``derivation=llm``) cannot claim hard evidence
    strength (``hard_static`` or ``hard_dynamic``).
    """

    source_tool: NonEmptyStr
    source_version: str | None = None
    source_run_id: str | None = None
    source_event_id: str | None = None
    repo: RepoRef
    snapshot: SnapshotRef
    file: str | None = None
    span: SourceSpan | None = None
    derivation: DerivationType
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    evidence_strength: EvidenceStrength
    created_ts: NonEmptyStr
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _llm_cannot_claim_hard_evidence(self) -> Provenance:
        """LLM derivation cannot have hard_static or hard_dynamic strength."""
        hard = {EvidenceStrength.hard_static, EvidenceStrength.hard_dynamic}
        if self.derivation == DerivationType.llm and self.evidence_strength in hard:
            raise ValueError(
                f"derivation=llm cannot claim "
                f"evidence_strength={self.evidence_strength.value}; "
                "LLM output is soft evidence until verified by a stronger source"
            )
        return self

    @model_validator(mode="after")
    def _repo_id_consistency(self) -> Provenance:
        """repo.repo_id must match snapshot.repo_id."""
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError(
                f"repo.repo_id {self.repo.repo_id!r} != "
                f"snapshot.repo_id {self.snapshot.repo_id!r}"
            )
        return self
