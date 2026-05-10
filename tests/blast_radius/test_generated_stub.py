"""Tests for generated-stub impact detection."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.generated_stub import build_generated_stub_notes
from llm_sca_tooling.blast_radius.models import GeneratedStubImpactType
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, ChangeKind


def _rec(
    file_path: str = "src/app.py",
    is_generated: bool = False,
    graph_node_id: str | None = None,
) -> ChangedSymbolRecord:
    return ChangedSymbolRecord(
        diff_id="diff-001",
        file_path=file_path,
        symbol_path="app.func",
        symbol_type="function",
        change_kind=ChangeKind.MODIFIED_BODY,
        is_generated=is_generated,
        graph_node_id=graph_node_id,
    )


class TestBuildGeneratedStubNotes:
    def test_non_generated_file_produces_no_note(self) -> None:
        rec = _rec(is_generated=False)
        notes = build_generated_stub_notes("d1", [rec])
        assert notes == []

    def test_generated_file_produces_note(self) -> None:
        rec = _rec(is_generated=True)
        notes = build_generated_stub_notes("d1", [rec])
        assert len(notes) == 1
        assert (
            notes[0].impact_type
            == GeneratedStubImpactType.GENERATED_FILE_DIRECTLY_CHANGED
        )

    def test_generated_file_sets_manual_edit_flag(self) -> None:
        rec = _rec(file_path="src/gen/service_pb2.py", is_generated=True)
        notes = build_generated_stub_notes("d1", [rec])
        assert notes[0].manual_edit_policy_flag is True

    def test_allowlisted_file_clears_manual_edit_flag(self) -> None:
        path = "src/gen/service_pb2.py"
        rec = _rec(file_path=path, is_generated=True)
        notes = build_generated_stub_notes("d1", [rec], generated_file_allowlist={path})
        assert notes[0].manual_edit_policy_flag is False

    def test_diff_id_propagated(self) -> None:
        rec = _rec(is_generated=True)
        notes = build_generated_stub_notes("my-diff", [rec])
        assert notes[0].diff_id == "my-diff"

    def test_graph_node_id_as_source_contract(self) -> None:
        rec = _rec(is_generated=True, graph_node_id="node:contract")
        notes = build_generated_stub_notes("d1", [rec])
        assert notes[0].source_contract_node_id == "node:contract"

    def test_multiple_generated_files(self) -> None:
        recs = [
            _rec(file_path="gen/a.py", is_generated=True),
            _rec(file_path="gen/b.py", is_generated=True),
            _rec(file_path="src/normal.py", is_generated=False),
        ]
        notes = build_generated_stub_notes("d2", recs)
        assert len(notes) == 2

    def test_empty_records(self) -> None:
        notes = build_generated_stub_notes("d1", [])
        assert notes == []
