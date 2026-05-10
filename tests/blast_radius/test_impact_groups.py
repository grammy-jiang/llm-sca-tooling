"""Tests for impact group population."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.impact_groups import (
    count_confirmed,
    group_impact_records,
)
from llm_sca_tooling.blast_radius.models import ImpactGroup, ImpactRecord


def _record(
    group: ImpactGroup, node_id: str = "node:1", confirmed: bool = True
) -> ImpactRecord:
    return ImpactRecord(
        group=group,
        node_id=node_id,
        node_type="function",
        hop_distance=1,
        confidence=0.9,
        confirmed=confirmed,
        edge_types_used=["calls"],
    )


class TestImpactGroupEnum:
    def test_all_eight_groups_present(self) -> None:
        values = {g.value for g in ImpactGroup}
        assert "direct_callers" in values
        assert "downstream_behaviours" in values
        assert "tests" in values
        assert "interfaces" in values
        assert "services" in values
        assert "repositories" in values
        assert "sarif_reachability" in values
        assert "linked_docs_specs" in values

    def test_exactly_eight_groups(self) -> None:
        assert len(ImpactGroup) == 8


class TestGroupImpactRecords:
    def test_empty_records_returns_all_groups_empty(self) -> None:
        groups = group_impact_records([])
        assert set(groups.keys()) == {g.value for g in ImpactGroup}
        for v in groups.values():
            assert v == []

    def test_single_direct_caller(self) -> None:
        rec = _record(ImpactGroup.DIRECT_CALLERS, "node:caller")
        groups = group_impact_records([rec])
        assert len(groups["direct_callers"]) == 1
        assert groups["direct_callers"][0]["node_id"] == "node:caller"

    def test_multiple_groups(self) -> None:
        records = [
            _record(ImpactGroup.DIRECT_CALLERS, "n:1"),
            _record(ImpactGroup.TESTS, "n:2"),
            _record(ImpactGroup.INTERFACES, "n:3"),
            _record(ImpactGroup.SARIF_REACHABILITY, "n:4"),
        ]
        groups = group_impact_records(records)
        assert len(groups["direct_callers"]) == 1
        assert len(groups["tests"]) == 1
        assert len(groups["interfaces"]) == 1
        assert len(groups["sarif_reachability"]) == 1
        assert len(groups["downstream_behaviours"]) == 0

    def test_serialised_as_dicts(self) -> None:
        rec = _record(ImpactGroup.REPOSITORIES, "n:repo")
        groups = group_impact_records([rec])
        item = groups["repositories"][0]
        assert isinstance(item, dict)
        assert item["node_id"] == "n:repo"

    def test_count_confirmed(self) -> None:
        records = [
            _record(ImpactGroup.DIRECT_CALLERS, "n:1", confirmed=True),
            _record(ImpactGroup.DIRECT_CALLERS, "n:2", confirmed=True),
            _record(ImpactGroup.TESTS, "n:3", confirmed=True),
        ]
        assert count_confirmed(records) == 3

    def test_count_confirmed_mixed(self) -> None:
        records = [
            _record(ImpactGroup.DIRECT_CALLERS, "n:a", confirmed=True),
            _record(ImpactGroup.DOWNSTREAM_BEHAVIOURS, "n:b", confirmed=False),
        ]
        assert count_confirmed(records) == 1
