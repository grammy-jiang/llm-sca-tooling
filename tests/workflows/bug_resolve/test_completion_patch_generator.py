"""CompletionPatchGenerator (queue item 1c)."""

from __future__ import annotations

import json

from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    CompletionPatchGenerator,
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


def test_diff_touching_undeclared_file_falls_back_to_null() -> None:
    """The diff itself is the authority — a lying changed_files list must
    not smuggle a patch that touches files outside the suspect set."""
    sneaky_diff = (
        "diff --git a/src/user_service.py b/src/user_service.py\n"
        "--- a/src/user_service.py\n+++ b/src/user_service.py\n"
        "@@ -1 +1 @@\n-old\n+fixed\n"
        "diff --git a/.github/workflows/publish.yml b/.github/workflows/publish.yml\n"
        "--- a/.github/workflows/publish.yml\n+++ b/.github/workflows/publish.yml\n"
        "@@ -1 +1 @@\n-safe\n+evil\n"
    )
    generator = CompletionPatchGenerator(
        complete=lambda p: json.dumps(
            {"diff_text": sneaky_diff, "changed_files": ["src/user_service.py"]}
        ),
        model_id="m1",
    )
    patch = generator.generate(_context())
    assert patch.generation_method == "null_repair"


def test_changed_files_derived_from_diff_not_model_claim() -> None:
    generator = CompletionPatchGenerator(
        complete=lambda p: json.dumps(
            {"diff_text": DIFF, "changed_files": ["src/other.py"]}  # model lies
        ),
        model_id="m1",
    )
    patch = generator.generate(_context())
    # DIFF touches only src/user_service.py; the model's claim is ignored.
    assert patch.changed_files == ["src/user_service.py"]
