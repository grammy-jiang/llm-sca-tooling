"""Workflow configuration for the Phase 13 bug-resolve workflow."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class WorkflowConfig(StrictBaseModel):
    """Configuration parameters controlling workflow execution."""

    max_candidates: int = Field(default=3, ge=1, le=20)
    max_repair_loops: int = Field(default=5, ge=1, le=50)
    max_gate_retries: int = Field(default=2, ge=0, le=10)
    context_budget: int = Field(default=8000, ge=1)
    token_budget: int = Field(default=120_000, ge=1)
    wall_clock_budget_seconds: int = Field(default=3600, ge=1)
    fl_budget: int = Field(default=10, ge=1, le=20)
    require_reproduction_test: bool = True
    require_blast_radius: bool = True
    require_patch_review: bool = True
    require_sarif_gate: bool = True
    require_interface_gate: bool = True
    null_mode: bool = False
    permission_profile: str = Field(default="scoped-execute", min_length=1)
    policy_id: str = Field(default="default", min_length=1)
    sandbox_only: bool = True


DEFAULT_WORKFLOW_CONFIG = WorkflowConfig()


__all__ = ["WorkflowConfig", "DEFAULT_WORKFLOW_CONFIG"]
