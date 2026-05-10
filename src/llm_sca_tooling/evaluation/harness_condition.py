"""Harness Condition Sheet model and renderers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from pydantic import Field

from llm_sca_tooling.evaluation.models import utc_now_ts
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class HarnessConditionSheet(StrictBaseModel):
    hcs_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    model_backend: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    manifest_hashes: dict[str, str]
    tool_set: list[str]
    tool_set_hash: str = Field(min_length=1)
    permission_mode: str = Field(min_length=1)
    sandbox_policy: str = Field(min_length=1)
    network_policy: str = Field(min_length=1)
    verification_gates: list[str]
    context_policy: str = Field(min_length=1)
    context_budget: int | None = Field(default=None, ge=0)
    retry_policy: str = Field(min_length=1)
    telemetry_location: str | None = None
    redaction_policy: str = Field(min_length=1)
    cost_limit: str | None = None
    harness_stage: str = Field(min_length=1)
    harness_drift_status: str = Field(min_length=1)
    created_ts: str = Field(default_factory=utc_now_ts)


def default_harness_condition_sheet(
    *,
    run_id: str,
    model_backend: str,
    tool_set: Iterable[str],
    permission_mode: str,
    manifest_hashes: dict[str, str] | None = None,
    verification_gates: Iterable[str] | None = None,
) -> HarnessConditionSheet:
    tools = sorted(set(tool_set))
    manifests = manifest_hashes or {"AGENTS.md": "current-worktree"}
    gates = sorted(set(verification_gates or ["pytest", "ruff", "mypy"]))
    tool_hash = _stable_hash(tools)
    hcs_hash = _stable_hash([run_id, model_backend, tool_hash, permission_mode])
    return HarnessConditionSheet(
        hcs_id=f"hcs:{hcs_hash[:24]}",
        run_id=run_id,
        model_backend=model_backend,
        model_version=model_backend,
        manifest_hashes=manifests,
        tool_set=tools,
        tool_set_hash=f"hash:{tool_hash}",
        permission_mode=permission_mode,
        sandbox_policy="workspace-write",
        network_policy="deny-by-default",
        verification_gates=gates,
        context_policy="phase10-null-eval",
        context_budget=None,
        retry_policy="3 attempts; doom-loop stop at 5 similar calls",
        telemetry_location="workspace operational store",
        redaction_policy="redacted",
        cost_limit="null-mode",
        harness_stage="S3",
        harness_drift_status="clean",
    )


def render_compact_hcs(sheet: HarnessConditionSheet) -> str:
    return (
        f"HCS {sheet.hcs_id}: model={sheet.model_backend}"
        f" tools={sheet.tool_set_hash} permission={sheet.permission_mode}"
        f" sandbox={sheet.sandbox_policy} network={sheet.network_policy}"
        f" gates={','.join(sheet.verification_gates)}"
        f" drift={sheet.harness_drift_status}"
    )


def render_key_value_hcs(sheet: HarnessConditionSheet) -> str:
    payload = sheet.model_dump(mode="json")
    return "\n".join(
        f"{key}={json.dumps(payload[key], sort_keys=True)}" for key in sorted(payload)
    )


def diff_harness_condition_sheets(
    before: HarnessConditionSheet, after: HarnessConditionSheet
) -> dict[str, JsonObject]:
    watched = {
        "model_backend",
        "model_version",
        "manifest_hashes",
        "tool_set",
        "tool_set_hash",
        "permission_mode",
        "verification_gates",
    }
    before_payload = before.model_dump(mode="json")
    after_payload = after.model_dump(mode="json")
    return {
        key: {"before": before_payload[key], "after": after_payload[key]}
        for key in sorted(watched)
        if before_payload[key] != after_payload[key]
    }


def _stable_hash(values: Iterable[object]) -> str:
    payload = json.dumps(list(values), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
