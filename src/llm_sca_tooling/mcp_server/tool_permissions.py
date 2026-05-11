"""Permission descriptor models for MCP tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ToolPermissionDescriptor"]


class ToolPermissionDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_mode: str
    path_scope: str
    network_requirement: str = "none"
    side_effect_class: str
    approval_requirement: str = "not_required"
    allowed_stages: list[str] = Field(default_factory=lambda: ["phase-4"])
    writes_to_store: bool = False
    writes_to_repo: bool = False
    runs_subprocesses: bool = False
