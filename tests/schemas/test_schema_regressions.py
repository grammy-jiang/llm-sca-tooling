"""Regression tests — field names and JSON schema shapes must not silently change."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.incidents import Incident
from llm_sca_tooling.schemas.json_schema import SCHEMA_MODELS, export_schema
from llm_sca_tooling.schemas.provenance import Provenance
from llm_sca_tooling.schemas.run_records import RunRecord

# -- Field presence regression --


def test_graph_node_required_fields():
    fields = GraphNode.model_fields
    for name in ("node_id", "repo", "snapshot", "node_type", "label", "provenance"):
        assert name in fields, f"GraphNode missing field: {name}"


def test_graph_edge_required_fields():
    fields = GraphEdge.model_fields
    for name in ("edge_id", "repo", "snapshot", "edge_type", "source_id", "target_id"):
        assert name in fields, f"GraphEdge missing field: {name}"


def test_provenance_required_fields():
    fields = Provenance.model_fields
    for name in ("derivation", "confidence", "evidence_strength"):
        assert name in fields, f"Provenance missing field: {name}"


def test_run_record_required_fields():
    fields = RunRecord.model_fields
    for name in ("run_id", "workflow", "status", "start_ts"):
        assert name in fields, f"RunRecord missing field: {name}"


def test_incident_required_fields():
    fields = Incident.model_fields
    for name in ("incident_id", "severity", "status", "title"):
        assert name in fields, f"Incident missing field: {name}"


# -- JSON schema export regression --


@pytest.mark.parametrize(
    "filename,family",
    [
        ("graph.schema.json", "graph"),
        ("evidence.schema.json", "evidence"),
        ("run-record.schema.json", "run-record"),
        ("governance.schema.json", "governance"),
    ],
)
def test_json_schemas_have_required_keys(filename: str, family: str):
    family_name, model, title, description = SCHEMA_MODELS[filename]
    schema = export_schema(model, family_name, title, description)
    assert "$schema" in schema, f"{family} schema missing $schema"
    assert "$id" in schema, f"{family} schema missing $id"
    assert "title" in schema, f"{family} schema missing title"
    assert "schema_version" in schema, f"{family} schema missing schema_version"


def test_all_schema_models_exportable():
    for filename, (family, model, title, description) in SCHEMA_MODELS.items():
        schema = export_schema(model, family, title, description)
        assert "title" in schema, f"{filename}: exported schema missing title"
        assert (
            "schema_version" in schema
        ), f"{filename}: exported schema missing schema_version"
