"""Tests for C/C++ ABI impact detection."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.abi_impact import build_abi_impact_notes
from llm_sca_tooling.blast_radius.models import ABIChangeType
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, ChangeKind


def _rec(
    file_path: str = "src/app.py",
    change_kind: ChangeKind = ChangeKind.MODIFIED_BODY,
    graph_node_id: str | None = None,
) -> ChangedSymbolRecord:
    return ChangedSymbolRecord(
        diff_id="diff-001",
        file_path=file_path,
        symbol_path="Foo::bar",
        symbol_type="method",
        change_kind=change_kind,
        graph_node_id=graph_node_id,
    )


class TestBuildABIImpactNotes:
    def test_python_file_skipped(self) -> None:
        rec = _rec(file_path="src/app.py")
        notes = build_abi_impact_notes([rec])
        assert notes == []

    def test_cpp_file_without_clangd_produces_unknown(self) -> None:
        rec = _rec(file_path="src/engine.cpp")
        notes = build_abi_impact_notes([rec], clangd_available=False)
        assert len(notes) == 1
        assert notes[0].abi_change_type == ABIChangeType.UNKNOWN

    def test_cpp_file_unknown_has_diagnostic(self) -> None:
        rec = _rec(file_path="src/engine.cpp")
        notes = build_abi_impact_notes([rec], clangd_available=False)
        assert len(notes[0].diagnostics) > 0
        assert "unavailable" in notes[0].diagnostics[0].lower()

    def test_c_extension_triggers_abi(self) -> None:
        for ext in [".c", ".h", ".hpp", ".cc", ".cxx", ".hxx"]:
            rec = _rec(file_path=f"src/engine{ext}")
            notes = build_abi_impact_notes([rec], clangd_available=False)
            assert len(notes) == 1, f"Expected note for {ext}"

    def test_with_clangd_signature_changed(self) -> None:
        rec = _rec(
            file_path="src/engine.cpp", change_kind=ChangeKind.MODIFIED_SIGNATURE
        )
        notes = build_abi_impact_notes([rec], clangd_available=True)
        assert len(notes) == 1
        assert notes[0].abi_change_type == ABIChangeType.SIGNATURE_CHANGED

    def test_with_clangd_body_change_is_no_impact(self) -> None:
        rec = _rec(file_path="src/engine.cpp", change_kind=ChangeKind.MODIFIED_BODY)
        notes = build_abi_impact_notes([rec], clangd_available=True)
        assert len(notes) == 1
        assert notes[0].abi_change_type == ABIChangeType.NO_ABI_IMPACT

    def test_graph_node_id_used_as_symbol_node_id(self) -> None:
        rec = _rec(file_path="src/engine.cpp", graph_node_id="node:cpp-sym")
        notes = build_abi_impact_notes([rec], clangd_available=False)
        assert notes[0].symbol_node_id == "node:cpp-sym"

    def test_fallback_to_symbol_path_when_no_node_id(self) -> None:
        rec = _rec(file_path="src/engine.cpp")
        notes = build_abi_impact_notes([rec], clangd_available=False)
        assert notes[0].symbol_node_id == "Foo::bar"

    def test_multiple_cpp_files(self) -> None:
        recs = [
            _rec(file_path="a.cpp"),
            _rec(file_path="b.cpp"),
            _rec(file_path="c.py"),
        ]
        notes = build_abi_impact_notes(recs, clangd_available=False)
        assert len(notes) == 2

    def test_empty_records(self) -> None:
        notes = build_abi_impact_notes([], clangd_available=False)
        assert notes == []
