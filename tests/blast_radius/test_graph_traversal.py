"""Tests for BFS graph traversal engine."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.change_type import ChangeType
from llm_sca_tooling.blast_radius.graph_traversal import traverse_graph
from llm_sca_tooling.blast_radius.traversal_policy import default_policy_for
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from tests.blast_radius.conftest import make_edge, make_node


def _setup_three_node_chain(workspace, repo_ref, snapshot, provenance):
    """Set up: changed -> caller -> downstream."""
    changed = make_node(
        "node:changed", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
    )
    caller = make_node(
        "node:caller", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
    )
    downstream = make_node(
        "node:downstream", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
    )
    workspace.graph.add_nodes([changed, caller, downstream])
    workspace.graph.add_edge(
        make_edge(
            "edge:caller-changed", caller, changed, provenance, GraphEdgeType.CALLS, 1.0
        )
    )
    workspace.graph.add_edge(
        make_edge(
            "edge:downstream-caller",
            downstream,
            caller,
            provenance,
            GraphEdgeType.CALLS,
            1.0,
        )
    )
    return changed, caller, downstream


class TestBFSTraversal:
    def test_direct_caller_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed, caller, _ = _setup_three_node_chain(
            workspace, repo_ref, snapshot, provenance
        )
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, ambiguous = traverse_graph(
            [changed.node_id], workspace.graph, policy, analyser_threshold=0.75
        )
        confirmed_ids = {r.node_id for r in confirmed}
        assert caller.node_id in confirmed_ids

    def test_downstream_detected_with_sufficient_hops(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed, caller, downstream = _setup_three_node_chain(
            workspace, repo_ref, snapshot, provenance
        )
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        confirmed_ids = {r.node_id for r in confirmed}
        assert downstream.node_id in confirmed_ids

    def test_hop_limit_respected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed, caller, downstream = _setup_three_node_chain(
            workspace, repo_ref, snapshot, provenance
        )
        # max_hops=1 should only find direct callers
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        one_hop = TraversalPolicy(
            change_type=ChangeType.INTERNAL_IMPLEMENTATION,
            max_hops=1,
            follow_edge_types=[GraphEdgeType.CALLS.value],
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, one_hop)
        confirmed_ids = {r.node_id for r in confirmed}
        assert caller.node_id in confirmed_ids
        assert downstream.node_id not in confirmed_ids

    def test_changed_nodes_not_in_output(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed, caller, _ = _setup_three_node_chain(
            workspace, repo_ref, snapshot, provenance
        )
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        confirmed_ids = {r.node_id for r in confirmed}
        assert changed.node_id not in confirmed_ids

    def test_low_confidence_edge_goes_to_ambiguous(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:c2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        weak_caller = make_node(
            "node:weak", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, weak_caller])
        workspace.graph.add_edge(
            make_edge(
                "edge:weak", weak_caller, changed, provenance, GraphEdgeType.CALLS, 0.3
            )
        )
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, ambiguous = traverse_graph(
            [changed.node_id], workspace.graph, policy, analyser_threshold=0.75
        )
        confirmed_ids = {r.node_id for r in confirmed}
        ambiguous_targets = {r.target_node_id for r in ambiguous}
        assert weak_caller.node_id not in confirmed_ids
        assert weak_caller.node_id in ambiguous_targets

    def test_interface_boundary_stops_internal_traversal(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:internal", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        boundary = make_node(
            "node:boundary", GraphNodeType.HTTP_ROUTE, repo_ref, snapshot, provenance
        )
        beyond = make_node(
            "node:beyond", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, boundary, beyond])
        workspace.graph.add_edge(
            make_edge(
                "edge:expose", changed, boundary, provenance, GraphEdgeType.EXPOSES, 1.0
            )
        )
        workspace.graph.add_edge(
            make_edge(
                "edge:beyond", boundary, beyond, provenance, GraphEdgeType.CALLS, 1.0
            )
        )
        policy = default_policy_for(ChangeType.INTERNAL_IMPLEMENTATION)
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        confirmed_ids = {r.node_id for r in confirmed}
        # boundary is included, but beyond is not (traversal stops at boundary)
        assert boundary.node_id in confirmed_ids
        assert beyond.node_id not in confirmed_ids

    def test_empty_changed_nodes_returns_empty(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, ambiguous = traverse_graph([], workspace.graph, policy)
        assert confirmed == []
        assert ambiguous == []

    def test_test_nodes_included_when_policy_allows(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        test_node = make_node(
            "node:test", GraphNodeType.TEST, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, test_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:test", test_node, changed, provenance, GraphEdgeType.TESTS, 1.0
            )
        )
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        confirmed_ids = {r.node_id for r in confirmed}
        assert test_node.node_id in confirmed_ids

    def test_test_nodes_excluded_when_policy_disallows(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        test_node = make_node(
            "node:test2", GraphNodeType.TEST, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, test_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:test2", test_node, changed, provenance, GraphEdgeType.TESTS, 1.0
            )
        )
        no_test_policy = TraversalPolicy(
            change_type=ChangeType.PUBLIC_API_CHANGE,
            max_hops=5,
            follow_edge_types=[GraphEdgeType.CALLS.value, GraphEdgeType.TESTS.value],
            include_test_nodes=False,
        )
        confirmed, _ = traverse_graph(
            [changed.node_id], workspace.graph, no_test_policy
        )
        confirmed_ids = {r.node_id for r in confirmed}
        assert test_node.node_id not in confirmed_ids

    def test_sarif_alert_node_classified_as_sarif_reachability(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn:sarif", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        sarif_node = make_node(
            "node:sarif:alert",
            GraphNodeType.SARIF_ALERT,
            repo_ref,
            snapshot,
            provenance,
        )
        workspace.graph.add_nodes([changed, sarif_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:sarif",
                changed,
                sarif_node,
                provenance,
                GraphEdgeType.WARNED_BY,
                1.0,
            )
        )
        policy = TraversalPolicy(
            change_type=ChangeType.PUBLIC_API_CHANGE,
            max_hops=3,
            follow_edge_types=[GraphEdgeType.WARNED_BY.value],
            include_sarif_reachability=True,
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        from llm_sca_tooling.blast_radius.models import ImpactGroup  # noqa: PLC0415

        sarif_records = [r for r in confirmed if r.node_id == sarif_node.node_id]
        assert sarif_records
        assert sarif_records[0].group == ImpactGroup.SARIF_REACHABILITY

    def test_sarif_node_excluded_when_policy_disallows(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn:sarif2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        sarif_node = make_node(
            "node:sarif:alert2",
            GraphNodeType.SARIF_ALERT,
            repo_ref,
            snapshot,
            provenance,
        )
        workspace.graph.add_nodes([changed, sarif_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:sarif2",
                changed,
                sarif_node,
                provenance,
                GraphEdgeType.WARNED_BY,
                1.0,
            )
        )
        policy = TraversalPolicy(
            change_type=ChangeType.PUBLIC_API_CHANGE,
            max_hops=3,
            follow_edge_types=[GraphEdgeType.WARNED_BY.value],
            include_sarif_reachability=False,
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        sarif_ids = {r.node_id for r in confirmed}
        assert sarif_node.node_id not in sarif_ids

    def test_doc_node_classified_as_linked_docs_specs(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn:doc", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        doc_node = make_node(
            "node:doc:spec", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, doc_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:doc", changed, doc_node, provenance, GraphEdgeType.DOCUMENTS, 1.0
            )
        )
        policy = TraversalPolicy(
            change_type=ChangeType.PUBLIC_API_CHANGE,
            max_hops=3,
            follow_edge_types=[GraphEdgeType.DOCUMENTS.value],
            include_doc_spec_links=True,
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        from llm_sca_tooling.blast_radius.models import ImpactGroup  # noqa: PLC0415

        doc_records = [r for r in confirmed if r.node_id == doc_node.node_id]
        assert doc_records
        assert doc_records[0].group == ImpactGroup.LINKED_DOCS_SPECS

    def test_doc_node_excluded_when_policy_disallows(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn:doc2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        doc_node = make_node(
            "node:doc:spec2", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, doc_node])
        workspace.graph.add_edge(
            make_edge(
                "edge:doc2", changed, doc_node, provenance, GraphEdgeType.DOCUMENTS, 1.0
            )
        )
        policy = TraversalPolicy(
            change_type=ChangeType.INTERNAL_IMPLEMENTATION,
            max_hops=3,
            follow_edge_types=[GraphEdgeType.DOCUMENTS.value],
            include_doc_spec_links=False,
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        doc_ids = {r.node_id for r in confirmed}
        assert doc_node.node_id not in doc_ids

    def test_non_matching_edge_type_skipped(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        """Edge whose type is not in follow_edge_types should be skipped (line 138-139)."""
        from llm_sca_tooling.blast_radius.traversal_policy import (  # noqa: PLC0415
            TraversalPolicy,
        )

        changed = make_node(
            "node:fn:skip", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        other = make_node(
            "node:other:skip", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, other])
        workspace.graph.add_edge(
            make_edge(
                "edge:skip", changed, other, provenance, GraphEdgeType.DATAFLOW, 1.0
            )
        )
        policy = TraversalPolicy(
            change_type=ChangeType.INTERNAL_IMPLEMENTATION,
            max_hops=3,
            # Only follow CALLS, not DATAFLOW
            follow_edge_types=[GraphEdgeType.CALLS.value],
        )
        confirmed, _ = traverse_graph([changed.node_id], workspace.graph, policy)
        other_ids = {r.node_id for r in confirmed}
        assert other.node_id not in other_ids
