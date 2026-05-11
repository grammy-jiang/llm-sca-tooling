"""Compatibility wrapper for Phase 5 cross-check terminology."""

from llm_sca_tooling.indexing.backends.fact_reconciler import (
    EvidenceAgreement,
)
from llm_sca_tooling.indexing.backends.fact_reconciler import (
    FactReconciler as CrossChecker,
)

__all__ = ["CrossChecker", "EvidenceAgreement"]
