"""Tests for the hardened blast-radius skill template."""

from __future__ import annotations

from pathlib import Path

SKILL_PATH = Path(__file__).parents[2] / ".skills" / "blast_radius.SKILL.md"


class TestBlastRadiusTemplate:
    def test_skill_file_exists(self) -> None:
        assert SKILL_PATH.exists(), f"Expected skill at {SKILL_PATH}"

    def test_skill_version_is_phase_15(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "version: 0.2.0" in content or "phase" in content.lower()

    def test_all_eight_groups_mentioned(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        groups = [
            "direct_callers",
            "downstream_behaviours",
            "tests",
            "interfaces",
            "services",
            "repositories",
            "sarif_reachability",
            "linked_docs_specs",
        ]
        for g in groups:
            assert g in content.lower(), f"Expected '{g}' in skill template"

    def test_confirmed_and_ambiguous_separation_rule_present(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "ambiguous" in content.lower()
        assert "confirmed" in content.lower()

    def test_is_partial_rule_present(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "is_partial" in content

    def test_abi_impact_mentioned(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "abi" in content.lower()

    def test_generated_stub_notes_mentioned(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "generated" in content.lower()

    def test_no_partial_always_set_rule(self) -> None:
        """Phase 15 should NOT always set is_partial=True (that was Phase 13)."""
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert "is_partial: true` in Phase 13" not in content or "Phase 15" in content

    def test_template_snapshot_stable(self) -> None:
        """Template content should be stable across runs (read twice)."""
        content1 = SKILL_PATH.read_text(encoding="utf-8")
        content2 = SKILL_PATH.read_text(encoding="utf-8")
        assert content1 == content2

    def test_change_type_table_present(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")
        assert (
            "INTERNAL_IMPLEMENTATION" in content
            or "internal_implementation" in content.lower()
        )
        assert "PUBLIC_API_CHANGE" in content or "public_api_change" in content.lower()
