"""Tool permission descriptors."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass


class ToolPermissionDescriptor(StrictBaseModel):
    required_mode: PermissionMode
    path_scope: str
    network_requirement: str = "none"
    side_effect_class: SideEffectClass
    approval_requirement: str = "not_required"
    allowed_stages: list[str] = Field(default_factory=lambda: ["S0", "S1", "S2", "S3"])
    writes_to_store: bool = False
    writes_to_repo: bool = False
    runs_subprocesses: bool = False
