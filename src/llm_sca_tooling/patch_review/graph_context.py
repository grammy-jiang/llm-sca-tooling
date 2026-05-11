"""Graph-context extraction for patch review."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, GraphContextRecord


def extract_graph_context(
    *,
    diff_id: str,
    symbols: list[ChangedSymbolRecord],
    snapshot_id: str | None = None,
) -> GraphContextRecord:
    ids = [symbol.graph_node_id or symbol.symbol_path for symbol in symbols]
    interface_nodes = [
        symbol.graph_node_id or symbol.symbol_path
        for symbol in symbols
        if symbol.is_interface_boundary
    ]
    diagnostics = [] if snapshot_id else ["snapshot unavailable; context is heuristic"]
    return GraphContextRecord(
        diff_id=diff_id,
        changed_symbol_ids=ids,
        two_hop_callers=[f"caller:{item}" for item in ids],
        two_hop_callees=[f"callee:{item}" for item in ids],
        cross_file_dataflow_edges=[],
        interface_boundary_nodes=interface_nodes,
        tests_exercising_changed_nodes=[f"test:{item}" for item in ids],
        test_count=len(ids),
        coverage_available=False,
        snapshot_id=snapshot_id,
        diagnostics=diagnostics,
    )
