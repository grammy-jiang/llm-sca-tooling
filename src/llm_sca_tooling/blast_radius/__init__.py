"""Phase 15 blast-radius service — cross-language and cross-repository impact analysis."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.change_type import ChangeType, classify_change_type
from llm_sca_tooling.blast_radius.models import (
    ABIChangeType,
    ABIImpactNote,
    AmbiguousLinkRecord,
    BlastRadiusConfig,
    BlastRadiusReport,
    CrossRepoImpactRecord,
    GeneratedStubImpactNote,
    GeneratedStubImpactType,
    ImpactGroup,
    ImpactRecord,
    MatchMethod,
)
from llm_sca_tooling.blast_radius.service import BlastRadiusService
from llm_sca_tooling.blast_radius.traversal_policy import (
    TraversalPolicy,
    default_policy_for,
)

__all__ = [
    "ABIChangeType",
    "ABIImpactNote",
    "AmbiguousLinkRecord",
    "BlastRadiusConfig",
    "BlastRadiusReport",
    "BlastRadiusService",
    "ChangeType",
    "CrossRepoImpactRecord",
    "GeneratedStubImpactNote",
    "GeneratedStubImpactType",
    "ImpactGroup",
    "ImpactRecord",
    "MatchMethod",
    "TraversalPolicy",
    "classify_change_type",
    "default_policy_for",
]
