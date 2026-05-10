"""Tests for the patch-generator interface and null adapter."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import GenerationMethod, RepairContext
from llm_sca_tooling.sast_repair.patch_generator import NullPatchGenerator


def test_null_patch_generator_produces_empty_diff() -> None:
    ctx = RepairContext(
        alert_id="a1",
        binding_ref="b:a1",
        classification_ref="c:a1",
        alert_explanation="explanation",
        predicate_examples_ref=["example:e1"],
        context_tokens_estimate=42,
    )
    generator = NullPatchGenerator()
    patch = generator.generate(ctx)
    assert patch.alert_id == "a1"
    assert patch.diff_text == ""
    assert patch.changed_files == []
    assert patch.generation_method is GenerationMethod.NULL_REPAIR
    assert patch.provenance["context_tokens"] == 42
    assert patch.provenance["examples_included"] == 1
