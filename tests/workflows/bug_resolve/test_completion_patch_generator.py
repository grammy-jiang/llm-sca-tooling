"""CompletionPatchGenerator (queue item 1c)."""

from __future__ import annotations

import json

from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    CompletionPatchGenerator,
    NullPatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.workflows.bug_resolve.models import RepairContextRecord

DIFF = (
    "diff --git a/src/user_service.py b/src/user_service.py\n"
    "--- a/src/user_service.py\n+++ b/src/user_service.py\n"
    "@@ -1 +1 @@\n-old\n+fixed\n"
)


def _context() -> RepairContextRecord:
    return RepairContextRecord(
        run_id="run:test",
        candidate_index=0,
        file_suspects=["src/user_service.py", "src/other.py"],
        graph_slices_ref="slices:run:test",
        summaries_ref="summaries:run:test",
    )


def test_is_a_patch_generator() -> None:
    generator = CompletionPatchGenerator(complete=lambda p: "{}", model_id="m1")
    assert isinstance(generator, PatchGeneratorInterface)


def test_valid_diff_within_suspects_is_accepted() -> None:
    def fake_complete(prompt: str) -> str:
        assert "src/user_service.py" in prompt
        return json.dumps(
            {
                "diff_text": DIFF,
                "changed_files": ["src/user_service.py"],
                "reasoning": ["null check added"],
            }
        )

    generator = CompletionPatchGenerator(complete=fake_complete, model_id="m1")
    patch = generator.generate(_context())
    assert patch.generation_method == "llm_completion"
    assert patch.generator_model == "m1"
    assert patch.changed_files == ["src/user_service.py"]
    assert patch.confidence == "unknown"  # hypothesis — gates decide


def test_changed_files_outside_suspects_fall_back_to_null() -> None:
    generator = CompletionPatchGenerator(
        complete=lambda p: json.dumps(
            {"diff_text": DIFF, "changed_files": ["src/invented.py"]}
        ),
        model_id="m1",
    )
    patch = generator.generate(_context())
    null_patch = NullPatchGenerator().generate(_context())
    assert patch.generation_method == null_patch.generation_method


def test_malformed_output_falls_back_to_null() -> None:
    generator = CompletionPatchGenerator(complete=lambda p: "not json", model_id="m1")
    patch = generator.generate(_context())
    assert patch.generation_method == "null_repair"


def test_non_diff_payload_falls_back_to_null() -> None:
    generator = CompletionPatchGenerator(
        complete=lambda p: json.dumps(
            {"diff_text": "just prose", "changed_files": ["src/user_service.py"]}
        ),
        model_id="m1",
    )
    patch = generator.generate(_context())
    assert patch.generation_method == "null_repair"
