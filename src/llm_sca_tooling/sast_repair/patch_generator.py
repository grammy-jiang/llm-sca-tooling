"""Patch generator interface and null adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.sast_repair.models import (
    ClassificationConfidence,
    GenerationMethod,
    RepairContext,
    SASTPatch,
)


class PatchGeneratorInterface(ABC):
    """Abstract LLM boundary for SAST patch generation."""

    model_id: str
    version: str

    @abstractmethod
    def generate(self, context: RepairContext) -> SASTPatch: ...


class NullPatchGenerator(PatchGeneratorInterface):
    """Deterministic null adapter used for pipeline smoke tests."""

    def __init__(
        self,
        *,
        model_id: str = "null-adapter",
        version: str = "0.1.0",
    ) -> None:
        self.model_id = model_id
        self.version = version

    def generate(self, context: RepairContext) -> SASTPatch:
        provenance = {
            "context_tokens": context.context_tokens_estimate,
            "examples_included": len(context.predicate_examples_ref),
            "model_id": self.model_id,
            "version": self.version,
        }
        return SASTPatch(
            alert_id=context.alert_id,
            diff_text="",
            diff_format="unified",
            changed_files=[],
            generator_model=self.model_id,
            generation_method=GenerationMethod.NULL_REPAIR,
            confidence=ClassificationConfidence.UNKNOWN,
            certificate_text=None,
            reasoning_chain=["null-adapter: no patch synthesised"],
            dryrun_prediction_ref=None,
            provenance=provenance,
        )


__all__ = ["PatchGeneratorInterface", "NullPatchGenerator"]
