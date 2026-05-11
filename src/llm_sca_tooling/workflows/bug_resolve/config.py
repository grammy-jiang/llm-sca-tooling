"""Workflow configuration factory."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import WorkflowConfig


def default_workflow_config(*, null_mode: bool = False) -> WorkflowConfig:
    return WorkflowConfig(null_mode=null_mode)
