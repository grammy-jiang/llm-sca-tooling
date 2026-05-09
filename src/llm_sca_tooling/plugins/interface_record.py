"""Interface contract records emitted by plugins."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.plugins.capability import ConfidenceLevel, InterfaceKind, OperationType
from llm_sca_tooling.schemas.base import JsonObject, SCHEMA_VERSION, StrictBaseModel, id_field, validate_repo_relative_path
from llm_sca_tooling.schemas.provenance import Provenance


class OperationParameter(StrictBaseModel):
    name: str = Field(min_length=1)
    location: str = Field(min_length=1)
    schema_: JsonObject | None = Field(default=None, alias="schema")
    required: bool = False
    nullable: bool = False


class GeneratedArtifactRecord(StrictBaseModel):
    artifact_id: str = id_field("Generated artifact identifier.")
    source_interface_id: str
    generator_tool: str
    file_paths: list[str] = Field(default_factory=list)
    is_checked_in: bool = True
    regeneration_command: str | None = None
    provenance: Provenance

    @field_validator("file_paths")
    @classmethod
    def validate_file_paths(cls, values: list[str]) -> list[str]:
        return [validate_repo_relative_path(value) for value in values]


class InterfaceOperation(StrictBaseModel):
    operation_id: str = id_field("Stable interface operation ID.")
    interface_id: str
    name: str = Field(min_length=1)
    operation_type: OperationType
    http_method: str | None = None
    path_pattern: str | None = None
    input_schema: JsonObject | None = None
    output_schema: JsonObject | None = None
    parameters: list[OperationParameter] = Field(default_factory=list)
    status_codes: list[int] | None = None
    auth_hints: list[str] | None = None
    server_handler_node_ids: list[str] = Field(default_factory=list)
    client_callsite_node_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    binding_method: str = Field(min_length=1)
    metadata: JsonObject = Field(default_factory=dict)


class InterfaceRecord(StrictBaseModel):
    schema_version: str = SCHEMA_VERSION
    interface_id: str = id_field("Stable interface identifier.")
    kind: InterfaceKind
    plugin_id: str
    plugin_version: str
    interface_name: str = Field(min_length=1)
    version: str | None = None
    definition_files: list[str] = Field(default_factory=list)
    source_repos: list[str] = Field(default_factory=list)
    operations: list[InterfaceOperation] = Field(default_factory=list)
    generated_artifacts: list[GeneratedArtifactRecord] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HEURISTIC
    snapshot_ids: dict[str, str] = Field(default_factory=dict)
    provenance: Provenance
    last_indexed_ts: str | None = None

    @field_validator("definition_files")
    @classmethod
    def validate_definition_files(cls, values: list[str]) -> list[str]:
        return [validate_repo_relative_path(value) for value in values]

    @model_validator(mode="after")
    def validate_record(self) -> "InterfaceRecord":
        for operation in self.operations:
            if operation.interface_id != self.interface_id:
                raise ValueError("operation interface_id must match InterfaceRecord")
        return self


def interface_id_for(plugin_id: str, kind: InterfaceKind, interface_name: str, repo_id: str) -> str:
    return f"interface:{hash_text(f'{plugin_id}|{kind.value}|{interface_name}|{repo_id}', length=32)}"


def operation_id_for(interface_id: str, operation_name: str, method: str | None = None) -> str:
    basis = f"{interface_id}|{operation_name}|{method or ''}"
    return f"operation:{hash_text(basis, length=32)}"
