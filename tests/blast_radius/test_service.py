"""Tests for BlastRadiusService — end-to-end including Phase 13 stub integration."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.change_type import ChangeType
from llm_sca_tooling.blast_radius.models import (
    ABIChangeType,
    BlastRadiusConfig,
    BlastRadiusReport,
    ImpactGroup,
)
from llm_sca_tooling.blast_radius.service import BlastRadiusService
from llm_sca_tooling.blast_radius.traversal_policy import (
    TraversalPolicy,
)
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, ChangeKind
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from tests.blast_radius.conftest import make_edge, make_node


def _rec(
    file_path: str = "src/app.py",
    symbol_path: str = "app.func",
    change_kind: ChangeKind = ChangeKind.MODIFIED_BODY,
    is_generated: bool = False,
    is_public_api: bool = False,
    graph_node_id: str | None = None,
) -> ChangedSymbolRecord:
    return ChangedSymbolRecord(
        diff_id="diff-001",
        file_path=file_path,
        symbol_path=symbol_path,
        symbol_type="function",
        change_kind=change_kind,
        is_generated=is_generated,
        is_public_api=is_public_api,
        graph_node_id=graph_node_id,
    )


class TestBlastRadiusServiceBasic:
    async def test_basic_report_returned(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        service = BlastRadiusService(workspace.graph)
        report = await service.compute(
            diff_id="d1",
            changed_symbol_records=[_rec()],
            run_id="r1",
        )
        assert isinstance(report, BlastRadiusReport)
        assert report.diff_id == "d1"
        assert report.run_id == "r1"

    async def test_empty_records_produces_report(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        service = BlastRadiusService(workspace.graph)
        report = await service.compute(
            diff_id="d2",
            changed_symbol_records=[],
            run_id="r2",
        )
        assert isinstance(report, BlastRadiusReport)
        # Unknown change type for empty records
        assert report.change_type == ChangeType.UNKNOWN.value

    async def test_generated_file_produces_note(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        service = BlastRadiusService(workspace.graph)
        rec = _rec(file_path="gen/service_pb2.py", is_generated=True)
        report = await service.compute(
            diff_id="d3", changed_symbol_records=[rec], run_id="r3"
        )
        assert len(report.generated_stub_notes) == 1
        assert report.generated_stub_notes[0].manual_edit_policy_flag is True

    async def test_cpp_file_produces_abi_note_when_clangd_absent(
        self, workspace
    ) -> None:
        service = BlastRadiusService(workspace.graph, clangd_available=False)
        rec = _rec(file_path="src/engine.cpp")
        report = await service.compute(
            diff_id="d4", changed_symbol_records=[rec], run_id="r4"
        )
        assert len(report.abi_impact_notes) == 1
        assert report.abi_impact_notes[0].abi_change_type == ABIChangeType.UNKNOWN
        assert report.is_partial is True

    async def test_partial_when_no_registered_repos_but_cross_repo_requested(
        self, workspace
    ) -> None:
        service = BlastRadiusService(
            workspace.graph,
            registered_repo_ids=[],  # empty
        )
        rec = _rec(is_public_api=True)  # -> PUBLIC_API_CHANGE -> cross_repo=True
        report = await service.compute(
            diff_id="d5", changed_symbol_records=[rec], run_id="r5"
        )
        assert report.is_partial is True

    async def test_config_overrides_max_hops(self, workspace) -> None:
        cfg = BlastRadiusConfig(max_hops_override=1)
        service = BlastRadiusService(workspace.graph, config=cfg)
        rec = _rec()
        report = await service.compute(
            diff_id="d6", changed_symbol_records=[rec], run_id="r6"
        )
        assert isinstance(report, BlastRadiusReport)

    async def test_compute_from_changed_symbols_with_change_type_override(
        self, workspace
    ) -> None:
        service = BlastRadiusService(workspace.graph)
        rec = _rec()
        report = await service.compute_from_changed_symbols(
            [rec],
            diff_id="d7",
            run_id="r7",
            change_type_override=ChangeType.SECURITY_SENSITIVE_CHANGE,
        )
        assert report.change_type == ChangeType.SECURITY_SENSITIVE_CHANGE.value

    async def test_compute_from_changed_symbols_with_policy_override(
        self, workspace
    ) -> None:
        service = BlastRadiusService(workspace.graph)
        rec = _rec()
        custom_policy = TraversalPolicy(
            change_type=ChangeType.PUBLIC_API_CHANGE,
            max_hops=2,
            follow_edge_types=["calls"],
        )
        report = await service.compute_from_changed_symbols(
            [rec],
            diff_id="d8",
            run_id="r8",
            policy_override=custom_policy,
        )
        assert isinstance(report, BlastRadiusReport)

    async def test_ambiguous_links_separate_from_confirmed(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:chg", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        weak_caller = make_node(
            "node:wcall", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, weak_caller])
        workspace.graph.add_edge(
            make_edge(
                "edge:weak", weak_caller, changed, provenance, GraphEdgeType.CALLS, 0.3
            )
        )

        rec = _rec(graph_node_id=changed.node_id)
        service = BlastRadiusService(workspace.graph)
        report = await service.compute(
            diff_id="d9", changed_symbol_records=[rec], run_id="r9"
        )

        # Weak caller should be in ambiguous, not in impact_groups
        all_confirmed_ids = {
            item["node_id"] for items in report.impact_groups.values() for item in items
        }
        assert weak_caller.node_id not in all_confirmed_ids
        ambiguous_targets = {a.target_node_id for a in report.ambiguous_links}
        assert weak_caller.node_id in ambiguous_targets

    async def test_direct_caller_in_direct_callers_group(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:main", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        caller = make_node(
            "node:c1", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, caller])
        workspace.graph.add_edge(
            make_edge(
                "edge:c1-main", caller, changed, provenance, GraphEdgeType.CALLS, 1.0
            )
        )
        rec = _rec(graph_node_id=changed.node_id)
        service = BlastRadiusService(workspace.graph)
        report = await service.compute(
            diff_id="d10", changed_symbol_records=[rec], run_id="r10"
        )
        caller_ids = {
            item["node_id"] for item in report.impact_groups.get("direct_callers", [])
        }
        assert caller.node_id in caller_ids

    async def test_compute_with_config_kwarg(self, workspace) -> None:
        cfg = BlastRadiusConfig(include_test_nodes=False)
        service = BlastRadiusService(workspace.graph)
        rec = _rec()
        report = await service.compute(
            diff_id="d11",
            changed_symbol_records=[rec],
            run_id="r11",
            config=cfg,
        )
        assert isinstance(report, BlastRadiusReport)

    async def test_report_has_all_eight_impact_groups(self, workspace) -> None:
        service = BlastRadiusService(workspace.graph)
        rec = _rec()
        report = await service.compute(
            diff_id="d12", changed_symbol_records=[rec], run_id="r12"
        )
        expected = {g.value for g in ImpactGroup}
        assert set(report.impact_groups.keys()) == expected


class TestPhase13Integration:
    """Verify BlastRadiusService can substitute for BlastRadiusStub."""

    async def test_service_produces_report_replacing_stub(self, workspace) -> None:
        """BlastRadiusReport has a superset of BlastRadiusStub fields."""
        service = BlastRadiusService(workspace.graph)
        rec = _rec(graph_node_id=None)
        report = await service.compute(
            diff_id="stub-diff", changed_symbol_records=[rec], run_id="stub-run"
        )
        # Fields formerly in BlastRadiusStub
        assert report.diff_id == "stub-diff"
        assert report.run_id == "stub-run"
        assert isinstance(report.ambiguous_links, list)
        assert isinstance(report.confirmed_impact_count, int)
        assert isinstance(report.is_partial, bool)

    async def test_stub_is_partial_preserved(self, workspace) -> None:
        """Real service sets is_partial when cross-repo is requested but unavailable."""
        service = BlastRadiusService(workspace.graph, registered_repo_ids=[])
        rec = _rec(is_public_api=True)  # triggers cross-repo policy
        report = await service.compute(
            diff_id="p13", changed_symbol_records=[rec], run_id="p13-run"
        )
        assert report.is_partial is True
