from __future__ import annotations

from llm_sca_tooling.schemas.supply_chain import ComponentType, SupplyChainRecord


def test_harness_metadata_active_and_history(workspace, registered_repo) -> None:
    first = workspace.harness.put_harness_metadata(
        registered_repo.repo_id, "manifest_hashes", {"AGENTS.md": "hash1"}
    )
    second = workspace.harness.put_harness_metadata(
        registered_repo.repo_id, "manifest_hashes", {"AGENTS.md": "hash2"}
    )
    active = workspace.harness.get_harness_metadata(
        registered_repo.repo_id, "manifest_hashes"
    )
    all_records = workspace.harness.get_harness_metadata(
        registered_repo.repo_id, "manifest_hashes", active_only=False
    )
    assert active[0].metadata_id == second.metadata_id
    assert {record.metadata_id for record in all_records} == {
        first.metadata_id,
        second.metadata_id,
    }


def test_supply_chain_records_list_by_component(
    workspace, registered_repo, provenance
) -> None:
    record = SupplyChainRecord(
        supply_chain_record_id="supply:semgrep",
        component_type=ComponentType.ANALYSER,
        name="semgrep",
        version="1.0",
        source="lockfile",
        captured_ts="2026-05-09T00:00:00Z",
        provenance=provenance,
    )
    workspace.harness.record_supply_chain_record(
        record, repo_id=registered_repo.repo_id
    )
    assert (
        workspace.harness.list_supply_chain_records(
            registered_repo.repo_id, ComponentType.ANALYSER
        )[0].name
        == "semgrep"
    )
