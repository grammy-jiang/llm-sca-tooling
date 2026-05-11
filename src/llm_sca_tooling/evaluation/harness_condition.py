"""Harness condition sheet renderer and comparer."""

from __future__ import annotations

import hashlib

from pydantic import Field, model_validator

from llm_sca_tooling.evaluation.models import StrictEvalModel, now_ts

__all__ = ["HarnessConditionSheet", "diff_sheets"]


class HarnessConditionSheet(StrictEvalModel):
    hcs_id: str
    run_id: str
    model_backend: str
    model_version: str
    manifest_hashes: dict[str, str]
    tool_set: list[str]
    tool_set_hash: str
    permission_mode: str
    sandbox_policy: str
    network_policy: str
    verification_gates: list[str]
    context_policy: str
    context_budget: int
    retry_policy: str
    telemetry_location: str
    redaction_policy: str
    cost_limit: int
    harness_stage: str
    harness_drift_status: str
    created_ts: str = Field(default_factory=now_ts)

    @model_validator(mode="after")
    def _required_identity(self) -> HarnessConditionSheet:
        if not self.model_backend or not self.manifest_hashes:
            raise ValueError("model_backend and manifest_hashes are required")
        return self

    @classmethod
    def create(
        cls, *, run_id: str, model_backend: str = "null"
    ) -> HarnessConditionSheet:
        tool_set = ["run_eval_suite", "compute_rds_features", "record_eval_result"]
        tool_hash = hashlib.sha256("|".join(tool_set).encode()).hexdigest()[:16]
        return cls(
            hcs_id=f"hcs:{run_id}",
            run_id=run_id,
            model_backend=model_backend,
            model_version="phase10-null",
            manifest_hashes={"AGENTS.md": "tracked"},
            tool_set=tool_set,
            tool_set_hash=tool_hash,
            permission_mode="read/search",
            sandbox_policy="local",
            network_policy="none",
            verification_gates=["ruff", "mypy", "pytest", "detect-secrets", "bandit"],
            context_policy="bounded",
            context_budget=8000,
            retry_policy="max3",
            telemetry_location=".agent/eval",
            redaction_policy="HC6",
            cost_limit=0,
            harness_stage="H0",
            harness_drift_status="clean",
        )

    def render_compact(self) -> str:
        return (
            f"{self.hcs_id}: model={self.model_backend}/{self.model_version}; "
            f"tools={self.tool_set_hash}; permission={self.permission_mode}; "
            f"gates={','.join(self.verification_gates)}"
        )

    def render_kv(self) -> str:
        return "\n".join(
            f"{key}={value}" for key, value in self.model_dump(mode="json").items()
        )


def diff_sheets(
    before: HarnessConditionSheet, after: HarnessConditionSheet
) -> dict[str, tuple[object, object]]:
    watched = [
        "model_backend",
        "manifest_hashes",
        "tool_set_hash",
        "permission_mode",
        "verification_gates",
    ]
    return {
        field: (getattr(before, field), getattr(after, field))
        for field in watched
        if getattr(before, field) != getattr(after, field)
    }
