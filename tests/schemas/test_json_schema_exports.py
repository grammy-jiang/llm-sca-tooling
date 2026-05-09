from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from llm_sca_tooling.schemas.json_schema import SCHEMA_MODELS, export_all


def test_exported_schema_files_exist_and_include_version() -> None:
    for filename in SCHEMA_MODELS:
        path = Path("schemas") / filename
        assert path.exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "0.1.0"
        assert payload["$schema"].startswith("https://json-schema.org/")


def test_schema_exports_are_stable(tmp_path: Path) -> None:
    export_all(tmp_path)
    for filename in SCHEMA_MODELS:
        assert (tmp_path / filename).read_text(encoding="utf-8") == (Path("schemas") / filename).read_text(encoding="utf-8")


def test_valid_graph_fixture_validates_against_exported_schema() -> None:
    schema = json.loads(Path("schemas/graph.schema.json").read_text(encoding="utf-8"))
    fixture = json.loads(Path("tests/schemas/fixtures/valid/graph-document.json").read_text(encoding="utf-8"))
    validate(instance=fixture, schema=schema)


def test_invalid_graph_fixture_fails_exported_schema() -> None:
    schema = json.loads(Path("schemas/graph.schema.json").read_text(encoding="utf-8"))
    fixture = json.loads(Path("tests/schemas/fixtures/invalid/graph-document-missing-provenance.json").read_text(encoding="utf-8"))
    with pytest.raises(JsonSchemaValidationError):
        validate(instance=fixture, schema=schema)
