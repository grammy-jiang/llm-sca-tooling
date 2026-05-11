"""Stage 3: Contract artefact generation and null adapter."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseGrounding,
    HarnessPolicyClause,
    ImplContractArtifact,
)


class ContractArtifactGenerator(ABC):
    artifact_type: str

    @abstractmethod
    def generate(
        self, clause: Clause | HarnessPolicyClause, grounding: ClauseGrounding
    ) -> ImplContractArtifact:
        raise NotImplementedError

    def compile_check(self, artifact: ImplContractArtifact) -> str:
        return "not_attempted"


class NullContractGenerator(ContractArtifactGenerator):
    artifact_type = "natural_language_probe"

    def generate(
        self, clause: Clause | HarnessPolicyClause, grounding: ClauseGrounding
    ) -> ImplContractArtifact:
        return ImplContractArtifact(
            artifact_id=f"artifact:{uuid.uuid4().hex[:8]}",
            clause_id=clause.clause_id,
            language="natural_language",
            artifact_type="natural_language_probe",
            target_symbols=grounding.symbol_node_ids[:3],
            source_clause_span=clause.source_span,
            compile_status="not_applicable",
            last_run_status="not_run",
            confidence=0.0,
            content=f"Does the implementation satisfy: {clause.text[:120]}?",
        )
