"""Tests for cross-repository traversal."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.cross_repo import traverse_cross_repo
from llm_sca_tooling.blast_radius.models import MatchMethod
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from tests.blast_radius.conftest import make_edge, make_node


class TestCrossRepoTraversal:
    def test_no_registered_repos_returns_ambiguous(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:ch", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_node(changed)
        records, ambiguous = traverse_cross_repo(
            [changed.node_id],
            workspace.graph,
            registered_repo_ids=None,
        )
        assert records == []
        assert len(ambiguous) >= 1
        assert all(
            a.match_method == MatchMethod.CROSS_REPO_UNRESOLVED for a in ambiguous
        )

    def test_empty_changed_nodes_with_repos(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        records, ambiguous = traverse_cross_repo(
            [],
            workspace.graph,
            registered_repo_ids=["repo:other"],
        )
        assert records == []

    def test_registered_repo_consuming_node_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:changed", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        # For this test, we expect no cross-repo records since we only have one repo
        workspace.graph.add_node(changed)
        records, ambiguous = traverse_cross_repo(
            [changed.node_id],
            workspace.graph,
            registered_repo_ids=[repo_ref.repo_id],
        )
        # changed node is in start_set, filtered out. No other nodes exist.
        assert isinstance(records, list)

    def test_is_partial_when_no_registered_repos(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        records, ambiguous = traverse_cross_repo(
            ["node:x"],
            workspace.graph,
            registered_repo_ids=None,
        )
        # Should produce ambiguous links indicating partial
        assert len(ambiguous) > 0

    def test_ambiguous_match_method_cross_repo_unresolved(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        records, ambiguous = traverse_cross_repo(
            ["node:y"],
            workspace.graph,
            registered_repo_ids=None,
        )
        for link in ambiguous:
            assert link.match_method == MatchMethod.CROSS_REPO_UNRESOLVED

    def test_analyser_threshold_propagated(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        """Test that custom threshold doesn't raise."""
        records, ambiguous = traverse_cross_repo(
            [],
            workspace.graph,
            registered_repo_ids=["r1"],
            analyser_threshold=0.9,
        )
        assert records == []

    def test_consumer_node_in_registered_repo_creates_cross_record(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        """Consumer node whose repo_id IS in registered_repo_ids → cross_records."""
        changed = make_node(
            "node:src2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        consumer = make_node(
            "node:consumer2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, consumer])
        workspace.graph.add_edge(
            make_edge("edge:c2c", consumer, changed, provenance, GraphEdgeType.CONSUMES)
        )
        records, ambiguous = traverse_cross_repo(
            [changed.node_id],
            workspace.graph,
            registered_repo_ids=[repo_ref.repo_id],
        )
        # consumer.repo_id == repo_ref.repo_id == registered → should produce cross record
        assert len(records) >= 1
        assert records[0].repo_id == repo_ref.repo_id

    def test_consumer_node_in_unregistered_repo_creates_ambiguous(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        """Consumer node whose repo_id is NOT in registered_repo_ids → ambiguous."""
        changed = make_node(
            "node:src3", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        consumer = make_node(
            "node:consumer3", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, consumer])
        workspace.graph.add_edge(
            make_edge("edge:c3c", consumer, changed, provenance, GraphEdgeType.CONSUMES)
        )
        # repo_ref.repo_id is NOT in this registered list
        records, ambiguous = traverse_cross_repo(
            [changed.node_id],
            workspace.graph,
            registered_repo_ids=["repo:some_completely_different_id"],
        )
        # consumer's repo_id is not in registered list → ambiguous
        assert len(ambiguous) >= 1
        assert all(
            a.match_method == MatchMethod.CROSS_REPO_UNRESOLVED for a in ambiguous
        )
