from __future__ import annotations

from llm_sca_tooling.workflows.impl_check.clause_extractor import extract_clauses
from llm_sca_tooling.workflows.impl_check.intent_graph import build_intent_graph


def test_build_intent_graph_returns_graph() -> None:
    clauses = extract_clauses("doc:i", "The system must work.\n")
    g = build_intent_graph("doc:i", clauses)
    assert g.graph_id.startswith("igraph:")
    assert g.doc_id == "doc:i"


def test_intent_nodes_count_matches() -> None:
    clauses = extract_clauses("doc:i", "The `a` must run.\nThe `b` must run.\n")
    g = build_intent_graph("doc:i", clauses)
    assert len(g.intent_nodes) == len(clauses)


def test_decomposes_to_edge_for_subclauses() -> None:
    clauses = extract_clauses(
        "doc:i", "The system must handle errors and notify users and log events.\n"
    )
    g = build_intent_graph("doc:i", clauses)
    assert any(e.get("type") == "decomposes_to" for e in g.decomposes_to_edges)


def test_graph_id_stable() -> None:
    clauses = extract_clauses("doc:i", "must work.\n")
    a = build_intent_graph("doc:i", clauses)
    b = build_intent_graph("doc:i", clauses)
    assert a.graph_id == b.graph_id


def test_snapshot_id_propagated() -> None:
    clauses = extract_clauses("doc:i", "must work.\n")
    g = build_intent_graph("doc:i", clauses, snapshot_id="snap:1")
    assert g.snapshot_id == "snap:1"
