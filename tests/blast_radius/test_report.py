"""Tests for BlastRadiusReport model and assembler."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.blast_radius.models import (
    ABIChangeType,
    ABIImpactNote,
    AmbiguousLinkRecord,
    BlastRadiusReport,
    CrossRepoImpactRecord,
    ImpactGroup,
    ImpactRecord,
    MatchMethod,
)
from llm_sca_tooling.blast_radius.report import assemble_report


def _impact_record(group: ImpactGroup = ImpactGroup.DIRECT_CALLERS) -> ImpactRecord:
    return ImpactRecord(
        group=group,
        node_id="node:x",
        node_type="function",
        hop_distance=1,
        confidence=0.9,
        confirmed=True,
        edge_types_used=["calls"],
    )


def _ambiguous_link() -> AmbiguousLinkRecord:
    return AmbiguousLinkRecord(
        source_node_id="n:src",
        target_node_id="n:tgt",
        edge_type="calls",
        confidence=0.3,
        match_method=MatchMethod.CANDIDATE_EDGE,
    )


class TestBlastRadiusReportModel:
    def test_model_round_trip(self) -> None:
        report = assemble_report(
            diff_id="diff-001",
            run_id="run-001",
            change_type="internal_implementation",
            traversal_policy_ref="internal_implementation",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        data = report.model_dump(mode="json")
        restored = BlastRadiusReport.model_validate(data)
        assert restored.diff_id == "diff-001"
        assert restored.run_id == "run-001"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            BlastRadiusReport.model_validate(
                {
                    "report_id": "blast-radius:abc",
                    "diff_id": "d",
                    "run_id": "r",
                    "change_type": "x",
                    "created_ts": "2026-01-01T00:00:00Z",
                    "unknown_field": True,
                }
            )

    def test_confirmed_and_ambiguous_counts(self) -> None:
        report = assemble_report(
            diff_id="d1",
            run_id="r1",
            change_type="public_api_change",
            traversal_policy_ref="public_api_change",
            confirmed_records=[_impact_record(), _impact_record(ImpactGroup.TESTS)],
            ambiguous_links=[_ambiguous_link()],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        assert report.confirmed_impact_count == 2
        assert report.ambiguous_impact_count == 1

    def test_ambiguous_links_separate_from_impact_groups(self) -> None:
        ambig = _ambiguous_link()
        report = assemble_report(
            diff_id="d2",
            run_id="r2",
            change_type="internal_implementation",
            traversal_policy_ref="internal_implementation",
            confirmed_records=[],
            ambiguous_links=[ambig],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        # Ambiguous links must NOT appear in impact_groups
        for group_items in report.impact_groups.values():
            assert all(
                isinstance(item, dict) and item.get("node_id") != ambig.target_node_id
                for item in group_items
            )
        assert len(report.ambiguous_links) == 1

    def test_partial_when_abi_unknown(self) -> None:
        abi_note = ABIImpactNote(
            symbol_node_id="n:sym",
            symbol_path="Foo::bar",
            abi_change_type=ABIChangeType.UNKNOWN,
            diagnostics=["clangd absent"],
        )
        report = assemble_report(
            diff_id="d3",
            run_id="r3",
            change_type="public_api_change",
            traversal_policy_ref="public_api_change",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[abi_note],
            cross_repo_impact_records=[],
        )
        assert report.is_partial is True
        assert "ABI" in report.partial_reason

    def test_partial_when_cross_repo_partial(self) -> None:
        xr = CrossRepoImpactRecord(
            repo_id="repo:other",
            consuming_node_ids=[],
            hop_distance=1,
            is_partial=True,
            partial_reason="overlay unavailable",
            confidence=0.0,
        )
        report = assemble_report(
            diff_id="d4",
            run_id="r4",
            change_type="public_api_change",
            traversal_policy_ref="public_api_change",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[xr],
        )
        assert report.is_partial is True

    def test_human_readable_summary_generated(self) -> None:
        report = assemble_report(
            diff_id="d5",
            run_id="r5",
            change_type="security_sensitive_change",
            traversal_policy_ref="security_sensitive_change",
            confirmed_records=[_impact_record()],
            ambiguous_links=[_ambiguous_link()],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        assert "security_sensitive_change" in report.human_readable_summary
        assert "1" in report.human_readable_summary

    def test_report_id_is_stable(self) -> None:
        report1 = assemble_report(
            diff_id="stable-diff",
            run_id="stable-run",
            change_type="internal_implementation",
            traversal_policy_ref="internal_implementation",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        report2 = assemble_report(
            diff_id="stable-diff",
            run_id="stable-run",
            change_type="internal_implementation",
            traversal_policy_ref="internal_implementation",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        assert report1.report_id == report2.report_id

    def test_impact_groups_has_all_eight_keys(self) -> None:
        report = assemble_report(
            diff_id="d6",
            run_id="r6",
            change_type="internal_implementation",
            traversal_policy_ref="internal_implementation",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
        )
        expected_keys = {g.value for g in ImpactGroup}
        assert set(report.impact_groups.keys()) == expected_keys

    def test_sarif_and_docs_summaries_propagated(self) -> None:
        report = assemble_report(
            diff_id="d7",
            run_id="r7",
            change_type="security_sensitive_change",
            traversal_policy_ref="security_sensitive_change",
            confirmed_records=[],
            ambiguous_links=[],
            generated_stub_notes=[],
            abi_impact_notes=[],
            cross_repo_impact_records=[],
            sarif_summary="3 SARIF alerts reachable.",
            linked_docs_summary="2 stale clauses.",
        )
        assert "3 SARIF" in report.sarif_reachability_summary
        assert "2 stale" in report.linked_docs_summary
