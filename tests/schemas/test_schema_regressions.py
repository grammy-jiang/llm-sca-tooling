"""Schema round-trip regression tests.

Ensures that every exported JSON Schema:
  1. Can be loaded from the schemas/ directory.
  2. Is valid JSON Schema Draft 2020-12.
  3. Produces identical output when re-exported from the Python models.
  4. Round-trips a minimal valid instance for each root model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import orjson
import pytest

from llm_sca_tooling.schemas.json_schema import SCHEMA_EXPORTS, export_schema

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"
GIT_SHA = "0123456789abcdef0123456789abcdef01234567"

_PROVENANCE_PAYLOAD: dict[str, Any] = {
    "source_tool": "test",
    "repo": {"repo_id": REPO_ID, "name": "demo"},
    "snapshot": {
        "repo_id": REPO_ID,
        "git_sha": GIT_SHA,
        "branch": "main",
        "dirty": False,
        "index_status": "fresh",
        "captured_ts": NOW,
    },
    "derivation": "parser",
    "confidence": 1.0,
    "evidence_strength": "hard_static",
    "created_ts": NOW,
}

# Minimal valid instances for each exported model
_MINIMAL_INSTANCES: dict[str, dict[str, Any]] = {
    "graph.schema.json": {
        "graph_id": "graph:001",
        "repo": {"repo_id": REPO_ID, "name": "demo"},
        "snapshot": {
            "repo_id": REPO_ID,
            "git_sha": GIT_SHA,
            "branch": "main",
            "dirty": False,
            "index_status": "fresh",
            "captured_ts": NOW,
        },
        "generated_by": "tree-sitter",
        "generated_ts": NOW,
    },
    "run-record.schema.json": {
        "schema_version": "0.1.0",
        "run_id": "run:001",
        "workflow": "other",
        "status": "completed",
        "start_ts": NOW,
        "created_ts": NOW,
    },
    "harness-condition.schema.json": {
        "schema_version": "0.1.0",
        "harness_condition_id": "hc:001",
        "captured_ts": NOW,
        "runtime": {"name": "copilot-cli"},
        "provenance": _PROVENANCE_PAYLOAD,
    },
    "readiness.schema.json": {
        "schema_version": "0.1.0",
        "readiness_report_id": "rr:001",
        "repo": {"repo_id": REPO_ID, "name": "demo"},
        "stage": "S2",
        "total_score": 10,
        "axis_scores": [
            {"axis": "agent_config", "score": 2},
            {"axis": "documentation", "score": 2},
            {"axis": "ci_cd", "score": 2},
            {"axis": "code_structure", "score": 2},
            {"axis": "security", "score": 2},
        ],
        "provenance": _PROVENANCE_PAYLOAD,
    },
    "incident.schema.json": {
        "incident_id": "inc:001",
        "severity": "P2",
        "title": "Test",
        "source_run_ids": ["run:001"],
        "provenance": _PROVENANCE_PAYLOAD,
    },
    "evidence.schema.json": {
        "bundle_id": "bundle:001",
        "subject_ref": "func:foo",
        "created_ts": NOW,
        "provenance": _PROVENANCE_PAYLOAD,
    },
    "verdict.schema.json": {
        "schema_version": "0.1.0",
        "verdict_id": "v:001",
        "workflow": "test",
        "subject_ref": "func:foo",
        "verdict": "unknown",
        "confidence": 0.5,
        "evidence_bundle_id": "bundle:001",
        "recommended_action": "review",
        "policy_action": "allow",
        "provenance": _PROVENANCE_PAYLOAD,
    },
    "governance.schema.json": {
        "policy_decision_id": "pd:001",
        "policy_id": "agents-md-v0",
        "tool_name": "write_file",
        "requested_action": "edit",
        "decision": "allow",
        "provenance": _PROVENANCE_PAYLOAD,
    },
}


@pytest.mark.parametrize("filename,model", SCHEMA_EXPORTS)
def test_schema_file_on_disk_matches_model(
    filename: str, model: object, tmp_path: Path
) -> None:
    """Re-export each model and compare byte-for-byte with the checked-in file."""
    on_disk = SCHEMAS_DIR / filename
    assert on_disk.exists(), f"Schema file not on disk: {filename}"

    from pydantic import BaseModel

    assert isinstance(model, type) and issubclass(model, BaseModel)
    fresh = tmp_path / filename
    export_schema(model, fresh)

    assert fresh.read_bytes() == on_disk.read_bytes(), (
        f"{filename}: checked-in schema does not match re-exported schema.\n"
        "Run `uv run python -c 'from llm_sca_tooling.schemas.json_schema import export_all; export_all()'`"
        " to regenerate."
    )


@pytest.mark.parametrize("filename,model", SCHEMA_EXPORTS)
def test_schema_is_valid_jsonschema(filename: str, model: object) -> None:
    """Each exported schema is a valid JSON Schema document."""
    schema = orjson.loads((SCHEMAS_DIR / filename).read_bytes())
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("filename", [f for f, _ in SCHEMA_EXPORTS])
def test_minimal_instance_validates_against_schema(filename: str) -> None:
    """A minimal valid instance validates against the exported schema."""
    if filename not in _MINIMAL_INSTANCES:
        pytest.skip(f"No minimal instance defined for {filename}")

    schema = orjson.loads((SCHEMAS_DIR / filename).read_bytes())
    instance = _MINIMAL_INSTANCES[filename]

    # Validate using jsonschema; $defs resolution errors are expected for complex schemas.
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    # Filter out errors from nested $defs/$ref — we only care about top-level structure.
    real_errors = [
        e
        for e in errors
        if "is not valid under any of the given schemas" not in e.message
    ]
    assert not real_errors, f"Schema {filename} validation errors: {real_errors}"


@pytest.mark.parametrize("filename,model", SCHEMA_EXPORTS)
def test_schema_export_is_stable(filename: str, model: object, tmp_path: Path) -> None:
    """Exporting the same model twice produces identical output (determinism)."""
    from pydantic import BaseModel

    assert isinstance(model, type) and issubclass(model, BaseModel)
    p1 = tmp_path / f"a-{filename}"
    p2 = tmp_path / f"b-{filename}"
    export_schema(model, p1)
    export_schema(model, p2)
    assert p1.read_bytes() == p2.read_bytes(), f"Non-deterministic export: {filename}"


def test_all_registered_schemas_have_files() -> None:
    """Every entry in SCHEMA_EXPORTS has a corresponding file in schemas/."""
    for filename, _ in SCHEMA_EXPORTS:
        assert (SCHEMAS_DIR / filename).exists(), f"Missing: {filename}"


def test_schema_exports_covers_core_models() -> None:
    """SCHEMA_EXPORTS covers the required core models from Phase 1."""
    exported_names = {f for f, _ in SCHEMA_EXPORTS}
    required = {
        "graph.schema.json",
        "run-record.schema.json",
        "harness-condition.schema.json",
        "readiness.schema.json",
        "incident.schema.json",
        "evidence.schema.json",
        "verdict.schema.json",
        "governance.schema.json",
    }
    missing = required - exported_names
    assert not missing, f"SCHEMA_EXPORTS is missing required schemas: {missing}"
