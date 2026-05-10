"""Graph-context extractor around changed symbols."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import (
    ChangedSymbolRecord,
    ConfidenceLevel,
    DiffRecord,
    GraphContextRecord,
)


def extract_graph_context(
    diff: DiffRecord,
    changed_symbols: list[ChangedSymbolRecord],
    *,
    callers: dict[str, list[str]] | None = None,
    callees: dict[str, list[str]] | None = None,
    dataflow_edges: list[dict[str, Any]] | None = None,
    tests_for_symbol: dict[str, list[str]] | None = None,
    coverage_available: bool = False,
    snapshot_id: str | None = None,
    snapshot_lag_commits: int | None = None,
) -> GraphContextRecord:
    """Aggregate two-hop callers/callees, dataflow edges, and tests.

    Inputs are pre-computed dicts so this module remains independent of
    the live indexing service. Missing test evidence is reported as
    ``coverage_available=False`` and ``confidence=unknown``.
    """
    callers = callers or {}
    callees = callees or {}
    tests_map = tests_for_symbol or {}
    diagnostics: list[dict[str, Any]] = []

    changed_ids: list[str] = [
        record.graph_node_id or record.symbol_path for record in changed_symbols
    ]
    two_hop_callers: list[str] = []
    two_hop_callees: list[str] = []
    interface_nodes: list[str] = []
    tests: list[str] = []
    seen_callers: set[str] = set()
    seen_callees: set[str] = set()
    seen_tests: set[str] = set()

    for record in changed_symbols:
        key = record.graph_node_id or record.symbol_path
        for hop1 in callers.get(key, []):
            if hop1 not in seen_callers:
                seen_callers.add(hop1)
                two_hop_callers.append(hop1)
            for hop2 in callers.get(hop1, []):
                if hop2 not in seen_callers:
                    seen_callers.add(hop2)
                    two_hop_callers.append(hop2)
        for hop1 in callees.get(key, []):
            if hop1 not in seen_callees:
                seen_callees.add(hop1)
                two_hop_callees.append(hop1)
            for hop2 in callees.get(hop1, []):
                if hop2 not in seen_callees:
                    seen_callees.add(hop2)
                    two_hop_callees.append(hop2)
        if record.is_interface_boundary:
            interface_nodes.append(key)
        for tid in tests_map.get(key, []):
            if tid not in seen_tests:
                seen_tests.add(tid)
                tests.append(tid)

    if not tests_map:
        diagnostics.append({"code": "no_test_evidence"})

    if snapshot_lag_commits is not None and snapshot_lag_commits > 1:
        diagnostics.append(
            {"code": "snapshot_stale", "lag_commits": snapshot_lag_commits}
        )

    confidence = (
        ConfidenceLevel.UNKNOWN
        if not (callers or callees)
        else ConfidenceLevel.ANALYSER
    )

    return GraphContextRecord(
        diff_id=diff.diff_id,
        changed_symbol_ids=changed_ids,
        two_hop_callers=two_hop_callers,
        two_hop_callees=two_hop_callees,
        cross_file_dataflow_edges=dataflow_edges or [],
        interface_boundary_nodes=interface_nodes,
        tests_exercising_changed_nodes=tests,
        test_count=len(tests),
        coverage_available=coverage_available,
        snapshot_id=snapshot_id,
        confidence=confidence,
        diagnostics=diagnostics,
    )
