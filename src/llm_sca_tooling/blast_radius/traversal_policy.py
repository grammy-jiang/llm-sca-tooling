"""Traversal policy factory for each change type."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.models import ChangeType, TraversalPolicy

_COMMON_EDGES = ["calls", "dataflow", "tests", "exposes", "consumes"]
_INTERFACE_EDGES = ["ffi", "implements", "exposes", "consumes"]
_ALL_EDGES = _COMMON_EDGES + _INTERFACE_EDGES + ["warns_by", "documents", "satisfies"]


_POLICIES: dict[ChangeType, TraversalPolicy] = {
    ChangeType.internal_implementation: TraversalPolicy(
        change_type=ChangeType.internal_implementation,
        max_hops=3,
        follow_edge_types=_COMMON_EDGES,
        stop_at_interface_boundary=True,
        include_cross_language=False,
        include_cross_repo=False,
        include_sarif_reachability=False,
        include_doc_spec_links=False,
    ),
    ChangeType.public_api_change: TraversalPolicy(
        change_type=ChangeType.public_api_change,
        max_hops=5,
        follow_edge_types=_COMMON_EDGES + _INTERFACE_EDGES,
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_sarif_reachability=False,
        include_doc_spec_links=False,
    ),
    ChangeType.idl_schema_contract_change: TraversalPolicy(
        change_type=ChangeType.idl_schema_contract_change,
        max_hops=6,
        follow_edge_types=_ALL_EDGES,
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_sarif_reachability=True,
        include_doc_spec_links=True,
    ),
    ChangeType.security_sensitive_change: TraversalPolicy(
        change_type=ChangeType.security_sensitive_change,
        max_hops=4,
        follow_edge_types=_ALL_EDGES,
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_sarif_reachability=True,
        include_doc_spec_links=False,
        depth_multiplier_security=1.5,
    ),
    ChangeType.generated_file_change: TraversalPolicy(
        change_type=ChangeType.generated_file_change,
        max_hops=2,
        follow_edge_types=_COMMON_EDGES,
        stop_at_interface_boundary=True,
        include_cross_language=False,
        include_cross_repo=False,
        include_sarif_reachability=False,
        include_doc_spec_links=False,
    ),
    ChangeType.mixed: TraversalPolicy(
        change_type=ChangeType.mixed,
        max_hops=6,
        follow_edge_types=_ALL_EDGES,
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_sarif_reachability=True,
        include_doc_spec_links=True,
    ),
    ChangeType.unknown: TraversalPolicy(
        change_type=ChangeType.unknown,
        max_hops=3,
        follow_edge_types=_COMMON_EDGES,
        stop_at_interface_boundary=True,
        include_cross_language=False,
        include_cross_repo=False,
    ),
}


def policy_for(change_type: ChangeType) -> TraversalPolicy:
    return _POLICIES.get(change_type, _POLICIES[ChangeType.unknown])
