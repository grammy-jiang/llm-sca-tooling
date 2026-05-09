"""Harness metadata and supply-chain stores."""

from __future__ import annotations

import json
from sqlite3 import Connection

from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel, canonical_json
from llm_sca_tooling.schemas.supply_chain import ComponentType, SupplyChainRecord
from llm_sca_tooling.storage.ids import payload_hash, stable_hash
from llm_sca_tooling.storage.workspace import _now_ts


class HarnessMetadataRecord(StrictBaseModel):
    metadata_id: str
    repo_id: str | None = None
    kind: str
    active: bool
    payload: JsonObject
    payload_hash: str
    created_ts: str
    updated_ts: str


class HarnessMetadataStore:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def put_harness_metadata(
        self,
        repo_id: str | None,
        kind: str,
        payload: JsonObject,
        *,
        active: bool = True,
    ) -> HarnessMetadataRecord:
        phash = payload_hash(payload)
        metadata_id = (
            f"hmeta:{stable_hash((repo_id or 'workspace') + ':' + kind + ':' + phash)}"
        )
        now = _now_ts()
        if active:
            if repo_id is None:
                self.conn.execute(
                    "UPDATE harness_metadata SET active=0 WHERE repo_id IS NULL AND kind=?",
                    (kind,),
                )
            else:
                self.conn.execute(
                    "UPDATE harness_metadata SET active=0 WHERE repo_id=? AND kind=?",
                    (repo_id, kind),
                )
        self.conn.execute(
            """
            INSERT INTO harness_metadata(metadata_id, repo_id, kind, active, payload_json, payload_hash, created_ts, updated_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metadata_id) DO UPDATE SET active=excluded.active, updated_ts=excluded.updated_ts
            """,
            (
                metadata_id,
                repo_id,
                kind,
                int(active),
                canonical_json(payload),
                phash,
                now,
                now,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM harness_metadata WHERE metadata_id=?", (metadata_id,)
        ).fetchone()
        return self._from_metadata_row(row)

    def get_harness_metadata(
        self, repo_id: str | None, kind: str, *, active_only: bool = True
    ) -> list[HarnessMetadataRecord]:
        if repo_id is None:
            clauses = ["repo_id IS NULL", "kind=?"]
            params: list[object] = [kind]
        else:
            clauses = ["repo_id=?", "kind=?"]
            params = [repo_id, kind]
        if active_only:
            clauses.append("active=1")
        return [
            self._from_metadata_row(row)
            for row in self.conn.execute(
                f"SELECT * FROM harness_metadata WHERE {' AND '.join(clauses)} ORDER BY updated_ts DESC, metadata_id",
                params,
            )
        ]

    def record_supply_chain_record(
        self, record: SupplyChainRecord, *, repo_id: str | None = None
    ) -> SupplyChainRecord:
        record = SupplyChainRecord.model_validate(record.model_dump(mode="python"))
        self.conn.execute(
            """
            INSERT INTO supply_chain_records(supply_chain_record_id, repo_id, component_type, name, version, source, hash, payload_json, captured_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(supply_chain_record_id) DO UPDATE SET payload_json=excluded.payload_json
            """,
            (
                record.supply_chain_record_id,
                repo_id,
                record.component_type.value,
                record.name,
                record.version,
                record.source,
                record.hash,
                record.model_dump_json(),
                record.captured_ts,
            ),
        )
        self.conn.commit()
        return record

    def list_supply_chain_records(
        self, repo_id: str | None = None, component_type: ComponentType | None = None
    ) -> list[SupplyChainRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if repo_id is not None:
            clauses.append("repo_id=?")
            params.append(repo_id)
        if component_type is not None:
            clauses.append("component_type=?")
            params.append(component_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            SupplyChainRecord.model_validate_json(row["payload_json"])
            for row in self.conn.execute(
                f"SELECT payload_json FROM supply_chain_records {where} ORDER BY captured_ts",
                params,
            )
        ]

    def _from_metadata_row(self, row) -> HarnessMetadataRecord:
        return HarnessMetadataRecord(
            metadata_id=row["metadata_id"],
            repo_id=row["repo_id"],
            kind=row["kind"],
            active=bool(row["active"]),
            payload=json.loads(row["payload_json"]),
            payload_hash=row["payload_hash"],
            created_ts=row["created_ts"],
            updated_ts=row["updated_ts"],
        )
