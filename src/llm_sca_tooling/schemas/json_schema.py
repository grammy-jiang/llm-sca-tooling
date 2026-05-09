"""Deterministic JSON Schema exports for Phase 1 contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, schema_extra
from llm_sca_tooling.schemas.evidence import EvidenceBundle
from llm_sca_tooling.schemas.governance import GovernanceDocument
from llm_sca_tooling.schemas.graph import GraphDocument
from llm_sca_tooling.schemas.harness import HarnessCondition
from llm_sca_tooling.schemas.incidents import Incident
from llm_sca_tooling.schemas.readiness import AIReadinessReport
from llm_sca_tooling.schemas.run_records import RunRecord
from llm_sca_tooling.schemas.verdicts import Verdict

SCHEMA_MODELS: dict[str, tuple[str, type[BaseModel], str, str]] = {
    "graph.schema.json": (
        "graph",
        GraphDocument,
        "Graph schema",
        "Repository intelligence graph document contract.",
    ),
    "run-record.schema.json": (
        "run-record",
        RunRecord,
        "Run record schema",
        "Run record and operational trace contract.",
    ),
    "evidence.schema.json": (
        "evidence",
        EvidenceBundle,
        "Evidence schema",
        "Evidence bundle contract.",
    ),
    "verdict.schema.json": (
        "verdict",
        Verdict,
        "Verdict schema",
        "Evidence-backed verdict contract.",
    ),
    "harness-condition.schema.json": (
        "harness-condition",
        HarnessCondition,
        "Harness condition schema",
        "Harness Condition Sheet contract.",
    ),
    "governance.schema.json": (
        "governance",
        GovernanceDocument,
        "Governance schema",
        "Policy and manifest governance contract.",
    ),
    "readiness.schema.json": (
        "readiness",
        AIReadinessReport,
        "Readiness schema",
        "AI-readiness report contract.",
    ),
    "incident.schema.json": (
        "incident",
        Incident,
        "Incident schema",
        "Operational incident contract.",
    ),
}


def export_schema(
    model: type[BaseModel], family: str, title: str, description: str
) -> dict:
    schema = model.model_json_schema(mode="validation")
    schema.update(schema_extra(family, title, description))
    schema["schema_version"] = SCHEMA_VERSION
    return schema


def export_all(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, (family, model, title, description) in sorted(SCHEMA_MODELS.items()):
        payload = export_schema(model, family, title, description)
        path = output_dir / filename
        path.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        written.append(path)
    return written


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    export_all(repo_root / "schemas")


if __name__ == "__main__":
    main()
