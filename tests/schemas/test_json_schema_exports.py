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


@pytest.mark.parametrize("schema_filename", sorted(SCHEMA_MODELS))
def test_valid_fixtures_validate_against_exported_schemas(schema_filename: str) -> None:
    schema = json.loads((Path("schemas") / schema_filename).read_text(encoding="utf-8"))
    fixture = json.loads((Path("tests/schemas/fixtures/valid") / _fixture_name(schema_filename)).read_text(encoding="utf-8"))
    validate(instance=fixture, schema=schema)
    SCHEMA_MODELS[schema_filename][1].model_validate(fixture)


@pytest.mark.parametrize("schema_filename", sorted(SCHEMA_MODELS))
def test_invalid_fixtures_fail_exported_schemas(schema_filename: str) -> None:
    schema = json.loads((Path("schemas") / schema_filename).read_text(encoding="utf-8"))
    fixture = json.loads((Path("tests/schemas/fixtures/invalid") / _fixture_name(schema_filename)).read_text(encoding="utf-8"))
    with pytest.raises(JsonSchemaValidationError):
        validate(instance=fixture, schema=schema)


def _fixture_name(schema_filename: str) -> str:
    return schema_filename.replace(".schema.json", ".json")
