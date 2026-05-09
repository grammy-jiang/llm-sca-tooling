"""Interface record persistence on top of the operational store."""

from __future__ import annotations

from llm_sca_tooling.plugins.interface_record import InterfaceRecord
from llm_sca_tooling.storage.operations import OperationalRecord
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


INTERFACE_RECORD_KIND = "interface_record"
PLUGIN_RUN_KIND = "plugin_run"


class InterfaceIndexStore:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def upsert_records(self, records: list[InterfaceRecord], *, run_id: str | None = None) -> None:
        for record in records:
            payload = record.model_dump(mode="json")
            payload["last_indexed_ts"] = record.last_indexed_ts or _now_ts()
            self.workspace.operations.record_operational_record(
                OperationalRecord(
                    record_id=f"interface:{record.plugin_id}:{record.interface_id}",
                    repo_id=record.source_repos[0] if record.source_repos else record.provenance.repo.repo_id,
                    run_id=run_id,
                    kind=INTERFACE_RECORD_KIND,
                    status="active",
                    payload=payload,
                )
            )

    def list_records(self, plugin_id: str | None = None, repo_id: str | None = None) -> list[InterfaceRecord]:
        records = []
        for row in self.workspace.operations.query_operational_records(repo_id=repo_id, kind=INTERFACE_RECORD_KIND):
            record = InterfaceRecord.model_validate(row.payload)
            if plugin_id is None or record.plugin_id == plugin_id:
                records.append(record)
        return records

    def get_record(self, plugin_id: str, interface_name: str) -> InterfaceRecord | None:
        for record in self.list_records(plugin_id=plugin_id):
            if record.interface_name == interface_name or record.interface_id == interface_name:
                return record
        return None
