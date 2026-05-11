"""Tests for JSON Schema export determinism and fixture validation."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import orjson
import pytest

from llm_sca_tooling.schemas.json_schema import (
    SCHEMA_EXPORTS,
    export_all,
    export_schema,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"


def test_schema_files_exist() -> None:
    for filename, _ in SCHEMA_EXPORTS:
        path = SCHEMAS_DIR / filename
        assert path.exists(), f"Missing exported schema: {filename}"


def test_schema_files_are_valid_json() -> None:
    for filename, _ in SCHEMA_EXPORTS:
        data = (SCHEMAS_DIR / filename).read_bytes()
        parsed = orjson.loads(data)
        assert isinstance(parsed, dict)


def test_schema_export_is_deterministic(tmp_path: Path) -> None:
    for filename, model in SCHEMA_EXPORTS:
        p1 = tmp_path / f"a-{filename}"
        p2 = tmp_path / f"b-{filename}"
        export_schema(model, p1)
        export_schema(model, p2)
        assert (
            p1.read_bytes() == p2.read_bytes()
        ), f"Non-deterministic export: {filename}"


def test_export_all_writes_registered_schemas(tmp_path: Path) -> None:
    export_all(tmp_path)
    assert sorted(path.name for path in tmp_path.glob("*.schema.json")) == sorted(
        filename for filename, _ in SCHEMA_EXPORTS
    )


def test_run_record_schema_has_required_fields() -> None:
    schema = orjson.loads((SCHEMAS_DIR / "run-record.schema.json").read_bytes())
    required = schema.get("required", [])
    assert "run_id" in required
    assert "created_ts" in required


def test_graph_schema_has_required_fields() -> None:
    schema = orjson.loads((SCHEMAS_DIR / "graph.schema.json").read_bytes())
    required = schema.get("required", [])
    assert "graph_id" in required
    assert "generated_by" in required


@pytest.mark.parametrize("filename,model", SCHEMA_EXPORTS)
def test_schema_is_valid_jsonschema_draft(filename: str, model: object) -> None:
    """Each exported schema is itself a valid JSON Schema document."""
    schema = orjson.loads((SCHEMAS_DIR / filename).read_bytes())
    # If the schema is well-formed, jsonschema.Draft202012Validator won't raise
    jsonschema.Draft202012Validator.check_schema(schema)
