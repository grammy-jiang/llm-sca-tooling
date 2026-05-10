"""Phase 15 traversal policy model and default policies per change type."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.blast_radius.change_type import ChangeType
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphEdgeType


class TraversalPolicy(StrictBaseModel):
    change_type: ChangeType
    max_hops: int = Field(ge=1)
    follow_edge_types: list[str] = Field(default_factory=list)
    stop_at_interface_boundary: bool = False
    include_cross_language: bool = False
    include_cross_repo: bool = False
    include_generated_files: bool = True
    include_test_nodes: bool = True
    include_sarif_reachability: bool = False
    include_doc_spec_links: bool = True
    depth_multiplier_security: float = Field(default=1.0, ge=1.0)
    confirmed_only: bool = False


_CALLER_CALLEE_EDGES = [
    GraphEdgeType.CALLS.value,
    GraphEdgeType.DATAFLOW.value,
]

_INTERFACE_EDGES = [
    GraphEdgeType.EXPOSES.value,
    GraphEdgeType.CONSUMES.value,
    GraphEdgeType.FFI.value,
    GraphEdgeType.IMPLEMENTS.value,
]

_TEST_EDGES = [GraphEdgeType.TESTS.value]

_DOC_EDGES = [
    GraphEdgeType.DOCUMENTS.value,
    GraphEdgeType.DECOMPOSES_TO.value,
    GraphEdgeType.SATISFIES.value,
    GraphEdgeType.VIOLATES.value,
]

_SARIF_EDGES = [GraphEdgeType.WARNED_BY.value]

_GENERATED_EDGES = [
    GraphEdgeType.FIXED_BY.value,
    GraphEdgeType.CHANGED_BY.value,
]

_ALL_STRUCTURAL = (
    _CALLER_CALLEE_EDGES
    + _INTERFACE_EDGES
    + _TEST_EDGES
    + _DOC_EDGES
    + _SARIF_EDGES
    + _GENERATED_EDGES
)


def _base_edges() -> list[str]:
    return list(_CALLER_CALLEE_EDGES + _INTERFACE_EDGES + _TEST_EDGES)


_DEFAULT_POLICIES: dict[ChangeType, TraversalPolicy] = {
    ChangeType.INTERNAL_IMPLEMENTATION: TraversalPolicy(
        change_type=ChangeType.INTERNAL_IMPLEMENTATION,
        max_hops=3,
        follow_edge_types=_base_edges() + _DOC_EDGES,
        stop_at_interface_boundary=True,
        include_cross_language=False,
        include_cross_repo=False,
        include_generated_files=True,
        include_test_nodes=True,
        include_sarif_reachability=False,
        include_doc_spec_links=True,
        depth_multiplier_security=1.0,
        confirmed_only=False,
    ),
    ChangeType.PUBLIC_API_CHANGE: TraversalPolicy(
        change_type=ChangeType.PUBLIC_API_CHANGE,
        max_hops=5,
        follow_edge_types=list(_ALL_STRUCTURAL),
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_generated_files=True,
        include_test_nodes=True,
        include_sarif_reachability=False,
        include_doc_spec_links=True,
        depth_multiplier_security=1.0,
        confirmed_only=False,
    ),
    ChangeType.IDL_SCHEMA_CONTRACT_CHANGE: TraversalPolicy(
        change_type=ChangeType.IDL_SCHEMA_CONTRACT_CHANGE,
        max_hops=6,
        follow_edge_types=list(_ALL_STRUCTURAL),
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_generated_files=True,
        include_test_nodes=True,
        include_sarif_reachability=True,
        include_doc_spec_links=True,
        depth_multiplier_security=1.0,
        confirmed_only=False,
    ),
    ChangeType.SECURITY_SENSITIVE_CHANGE: TraversalPolicy(
        change_type=ChangeType.SECURITY_SENSITIVE_CHANGE,
        max_hops=4,
        follow_edge_types=list(_ALL_STRUCTURAL),
        stop_at_interface_boundary=False,
        include_cross_language=True,
        include_cross_repo=True,
        include_generated_files=True,
        include_test_nodes=True,
        include_sarif_reachability=True,
        include_doc_spec_links=True,
        depth_multiplier_security=1.5,
        confirmed_only=False,
    ),
    ChangeType.GENERATED_FILE_CHANGE: TraversalPolicy(
        change_type=ChangeType.GENERATED_FILE_CHANGE,
        max_hops=2,
        follow_edge_types=_base_edges() + _GENERATED_EDGES,
        stop_at_interface_boundary=True,
        include_cross_language=False,
        include_cross_repo=False,
        include_generated_files=True,
        include_test_nodes=True,
        include_sarif_reachability=False,
        include_doc_spec_links=False,
        depth_multiplier_security=1.0,
        confirmed_only=False,
    ),
}


def default_policy_for(
    change_type: ChangeType,
    applicable_types: list[ChangeType] | None = None,
) -> TraversalPolicy:
    """Return the default traversal policy for the given change type.

    For MIXED, produces a combined policy taking the maximum of applicable types.
    """
    if change_type == ChangeType.MIXED:
        candidates = applicable_types or []
        policies = [
            _DEFAULT_POLICIES.get(ct, _DEFAULT_POLICIES[ChangeType.PUBLIC_API_CHANGE])
            for ct in candidates
            if ct != ChangeType.MIXED
        ]
        if not policies:
            return _DEFAULT_POLICIES[ChangeType.PUBLIC_API_CHANGE]
        max_hops = max(p.max_hops for p in policies)
        cross_lang = any(p.include_cross_language for p in policies)
        cross_repo = any(p.include_cross_repo for p in policies)
        sarif = any(p.include_sarif_reachability for p in policies)
        edge_types: set[str] = set()
        for p in policies:
            edge_types.update(p.follow_edge_types)
        return TraversalPolicy(
            change_type=ChangeType.MIXED,
            max_hops=max_hops,
            follow_edge_types=sorted(edge_types),
            stop_at_interface_boundary=False,
            include_cross_language=cross_lang,
            include_cross_repo=cross_repo,
            include_generated_files=True,
            include_test_nodes=True,
            include_sarif_reachability=sarif,
            include_doc_spec_links=True,
            depth_multiplier_security=max(
                p.depth_multiplier_security for p in policies
            ),
            confirmed_only=False,
        )

    if change_type == ChangeType.UNKNOWN:
        return _DEFAULT_POLICIES[ChangeType.INTERNAL_IMPLEMENTATION]

    return _DEFAULT_POLICIES.get(
        change_type, _DEFAULT_POLICIES[ChangeType.INTERNAL_IMPLEMENTATION]
    )


__all__ = ["TraversalPolicy", "default_policy_for"]
