"""Tests for TraversalPolicy model and default policies."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.blast_radius.change_type import ChangeType
from llm_sca_tooling.blast_radius.traversal_policy import (
    TraversalPolicy,
    default_policy_for,
)
from llm_sca_tooling.schemas.enums import GraphEdgeType


class TestTraversalPolicyModel:
    def test_model_round_trip(self) -> None:
        policy = TraversalPolicy(
            change_type=ChangeType.INTERNAL_IMPLEMENTATION,
            max_hops=3,
            follow_edge_types=["calls"],
            stop_at_interface_boundary=True,
        )
        data = policy.model_dump(mode="json")
        restored = TraversalPolicy.model_validate(data)
        assert restored.max_hops == 3
        assert restored.stop_at_interface_boundary is True

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            TraversalPolicy.model_validate(
                {
                    "change_type": "internal_implementation",
                    "max_hops": 3,
                    "unknown_field": True,
                }
            )

    def test_max_hops_minimum(self) -> None:
        with pytest.raises(ValidationError):
            TraversalPolicy(
                change_type=ChangeType.INTERNAL_IMPLEMENTATION,
                max_hops=0,
            )


class TestDefaultPolicies:
    def test_internal_implementation_stops_at_boundary(self) -> None:
        policy = default_policy_for(ChangeType.INTERNAL_IMPLEMENTATION)
        assert policy.stop_at_interface_boundary is True
        assert policy.include_cross_language is False
        assert policy.include_cross_repo is False
        assert policy.include_sarif_reachability is False
        assert policy.max_hops == 3

    def test_public_api_change_traverses_cross_repo(self) -> None:
        policy = default_policy_for(ChangeType.PUBLIC_API_CHANGE)
        assert policy.include_cross_language is True
        assert policy.include_cross_repo is True
        assert policy.stop_at_interface_boundary is False
        assert policy.max_hops == 5

    def test_idl_schema_includes_sarif(self) -> None:
        policy = default_policy_for(ChangeType.IDL_SCHEMA_CONTRACT_CHANGE)
        assert policy.include_sarif_reachability is True
        assert policy.include_cross_language is True
        assert policy.include_cross_repo is True
        assert policy.max_hops == 6

    def test_security_includes_sarif(self) -> None:
        policy = default_policy_for(ChangeType.SECURITY_SENSITIVE_CHANGE)
        assert policy.include_sarif_reachability is True
        assert policy.depth_multiplier_security > 1.0
        assert policy.max_hops == 4

    def test_generated_file_minimal_hops(self) -> None:
        policy = default_policy_for(ChangeType.GENERATED_FILE_CHANGE)
        assert policy.max_hops == 2
        assert policy.include_cross_language is False
        assert policy.include_cross_repo is False
        assert policy.stop_at_interface_boundary is True

    def test_unknown_falls_back_to_internal(self) -> None:
        policy = default_policy_for(ChangeType.UNKNOWN)
        internal = default_policy_for(ChangeType.INTERNAL_IMPLEMENTATION)
        assert policy.max_hops == internal.max_hops

    def test_mixed_takes_max_hops(self) -> None:
        policy = default_policy_for(
            ChangeType.MIXED,
            applicable_types=[
                ChangeType.INTERNAL_IMPLEMENTATION,
                ChangeType.PUBLIC_API_CHANGE,
            ],
        )
        assert policy.max_hops == 5  # max of 3 and 5

    def test_mixed_enables_cross_repo_if_any(self) -> None:
        policy = default_policy_for(
            ChangeType.MIXED,
            applicable_types=[
                ChangeType.INTERNAL_IMPLEMENTATION,
                ChangeType.IDL_SCHEMA_CONTRACT_CHANGE,
            ],
        )
        assert policy.include_cross_repo is True

    def test_mixed_enables_sarif_if_any(self) -> None:
        policy = default_policy_for(
            ChangeType.MIXED,
            applicable_types=[
                ChangeType.INTERNAL_IMPLEMENTATION,
                ChangeType.SECURITY_SENSITIVE_CHANGE,
            ],
        )
        assert policy.include_sarif_reachability is True

    def test_mixed_with_no_applicable_falls_back(self) -> None:
        policy = default_policy_for(ChangeType.MIXED, applicable_types=[])
        # Should fall back to PUBLIC_API_CHANGE
        assert policy.max_hops == 5

    def test_mixed_edge_types_are_union(self) -> None:
        policy = default_policy_for(
            ChangeType.MIXED,
            applicable_types=[
                ChangeType.INTERNAL_IMPLEMENTATION,
                ChangeType.PUBLIC_API_CHANGE,
            ],
        )
        # Union should contain calls at minimum
        assert GraphEdgeType.CALLS.value in policy.follow_edge_types

    def test_all_change_types_have_policy(self) -> None:
        for ct in ChangeType:
            policy = default_policy_for(ct)
            assert policy.max_hops >= 1
