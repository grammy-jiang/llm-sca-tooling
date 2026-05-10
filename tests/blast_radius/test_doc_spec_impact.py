"""Tests for doc/spec impact collection."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.doc_spec_impact import collect_linked_docs
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from tests.blast_radius.conftest import make_edge, make_node


class TestCollectLinkedDocs:
    def test_empty_changed_nodes_returns_empty(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        docs, summary = collect_linked_docs([], workspace.graph)
        assert docs == []
        assert "No linked" in summary

    def test_no_doc_nodes_returns_empty(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        workspace.graph.add_node(changed)
        docs, summary = collect_linked_docs([changed.node_id], workspace.graph)
        assert docs == []
        assert "No linked" in summary

    def test_document_node_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn2", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        doc = make_node(
            "node:doc1", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, doc])
        workspace.graph.add_edge(
            make_edge("edge:doc1", changed, doc, provenance, GraphEdgeType.DOCUMENTS)
        )
        docs, summary = collect_linked_docs([changed.node_id], workspace.graph)
        doc_ids = [d["node_id"] for d in docs]
        assert doc.node_id in doc_ids
        assert "1 linked" in summary

    def test_design_clause_node_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn3", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        clause = make_node(
            "node:clause1", GraphNodeType.DESIGN_CLAUSE, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, clause])
        workspace.graph.add_edge(
            make_edge("edge:sat1", changed, clause, provenance, GraphEdgeType.SATISFIES)
        )
        docs, summary = collect_linked_docs([changed.node_id], workspace.graph)
        doc_ids = [d["node_id"] for d in docs]
        assert clause.node_id in doc_ids

    def test_intent_node_detected(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn4", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        intent = make_node(
            "node:intent1", GraphNodeType.INTENT_NODE, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, intent])
        workspace.graph.add_edge(
            make_edge("edge:vio1", changed, intent, provenance, GraphEdgeType.VIOLATES)
        )
        docs, summary = collect_linked_docs([changed.node_id], workspace.graph)
        doc_ids = [d["node_id"] for d in docs]
        assert intent.node_id in doc_ids

    def test_potentially_stale_is_true(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn5", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        doc = make_node(
            "node:doc2", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, doc])
        workspace.graph.add_edge(
            make_edge("edge:doc2", changed, doc, provenance, GraphEdgeType.DOCUMENTS)
        )
        docs, _ = collect_linked_docs([changed.node_id], workspace.graph)
        assert all(d["potentially_stale"] is True for d in docs)

    def test_multiple_doc_nodes_summary_count(
        self, workspace, repo_ref, snapshot, provenance
    ) -> None:
        changed = make_node(
            "node:fn6", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance
        )
        doc1 = make_node(
            "node:doc3", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        doc2 = make_node(
            "node:doc4", GraphNodeType.DOCUMENT, repo_ref, snapshot, provenance
        )
        workspace.graph.add_nodes([changed, doc1, doc2])
        workspace.graph.add_edge(
            make_edge("edge:d3", changed, doc1, provenance, GraphEdgeType.DOCUMENTS)
        )
        workspace.graph.add_edge(
            make_edge("edge:d4", changed, doc2, provenance, GraphEdgeType.DOCUMENTS)
        )
        docs, summary = collect_linked_docs([changed.node_id], workspace.graph)
        assert len(docs) == 2
        assert "2 linked" in summary
