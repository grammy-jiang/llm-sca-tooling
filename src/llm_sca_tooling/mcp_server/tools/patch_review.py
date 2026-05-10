"""Phase 11 patch-review MCP tool handlers."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.patch_review.report import (
    classify_patch_risk as _classify_patch_risk,
)
from llm_sca_tooling.patch_review.report import run_patch_review as _run_patch_review
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import (
    ArtifactKind,
    PermissionMode,
    RedactionStatus,
    SideEffectClass,
)
from llm_sca_tooling.schemas.provenance import ArtifactRef
from llm_sca_tooling.storage.workspace import _now_ts


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _diff_text(args: JsonObject) -> str:
    diff = args.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        raise ToolInvalidArguments("diff is required")
    return diff


def _opt_str(args: JsonObject, key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInvalidArguments(f"{key} must be a string")
    return value


def _opt_dict_list(args: JsonObject, key: str) -> list[dict[str, Any]] | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolInvalidArguments(f"{key} must be a list of objects")
    return [dict(item) for item in value if isinstance(item, dict)]


def _opt_str_dict(args: JsonObject, key: str) -> dict[str, str] | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolInvalidArguments(f"{key} must be an object")
    return {str(k): str(v) for k, v in value.items()}


def _opt_str_list(args: JsonObject, key: str) -> list[str] | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolInvalidArguments(f"{key} must be a list of strings")
    return [str(item) for item in value]


def _store_artifact(context: McpRequestContext, payload: str, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    artifact_dir = context.workspace.artifact_root / "patch_review"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{kind}_{digest[:24]}.json"
    path.write_text(payload + "\n", encoding="utf-8")
    ref = ArtifactRef(
        artifact_id=f"art:patch-review-{kind}:{digest[:24]}",
        kind=ArtifactKind.REPORT,
        uri=str(path),
        sha256=digest,
        size_bytes=path.stat().st_size,
        media_type="application/json",
        redaction_status=RedactionStatus.REDACTED,
        created_ts=_now_ts(),
    )
    return context.workspace.artifacts.record_artifact(
        ref, repo_id=None, payload_path=Path(path)
    )


_RUN_PATCH_REVIEW_INPUT = _schema(
    {
        "diff": {"type": "string"},
        "context": {"type": "object"},
        "repos": {"type": "array", "items": {"type": "string"}},
        "policy": {"type": "object"},
        "run_id": {"type": "string"},
        "sampling_enabled": {"type": "boolean"},
        "sarif_appeared": {"type": "array", "items": {"type": "object"}},
        "sarif_disappeared": {"type": "array", "items": {"type": "object"}},
        "sarif_severity_changed": {"type": "array", "items": {"type": "object"}},
        "sarif_available": {"type": "boolean"},
        "test_results_before": {"type": "object"},
        "test_results_after": {"type": "object"},
        "interface_records": {"type": "array", "items": {"type": "object"}},
        "run_events": {"type": "array", "items": {"type": "object"}},
        "allowlisted_paths": {"type": "array", "items": {"type": "string"}},
        "required_tests": {"type": "array", "items": {"type": "string"}},
        "poc_required": {"type": "boolean"},
        "calibration_family": {"type": "string"},
        "intended_behaviour_change": {"type": "string"},
        "actual_files_changed": {"type": "array", "items": {"type": "string"}},
        "actual_side_effects": {"type": "array", "items": {"type": "string"}},
        "invariants_violated": {"type": "array", "items": {"type": "string"}},
        "risks_materialised": {"type": "array", "items": {"type": "string"}},
        "incident_ids": {"type": "array", "items": {"type": "string"}},
        "permission_mode": {"type": "string"},
        "budget_hard_stop": {"type": "boolean"},
        "trace_complete": {"type": "boolean"},
    },
    ["diff"],
)


class RunPatchReviewTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_patch_review",
        description=(
            "Phase 11 deterministic+four-agent patch-review entrypoint. "
            "Combines diff parsing, SARIF/test/interface deltas, scope audit, "
            "maintainability gate, and Sampling-with-fallback four-axis review "
            "into a typed PatchReviewReport with HCS reference."
        ),
        input_schema=_RUN_PATCH_REVIEW_INPUT,
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        diff = _diff_text(args)
        report, sheet = asyncio.run(
            _run_patch_review(
                diff=diff,
                run_id=_opt_str(args, "run_id"),
                sampling_enabled=bool(args.get("sampling_enabled", False)),
                sarif_appeared=_opt_dict_list(args, "sarif_appeared"),
                sarif_disappeared=_opt_dict_list(args, "sarif_disappeared"),
                sarif_severity_changed=_opt_dict_list(args, "sarif_severity_changed"),
                sarif_available=bool(args.get("sarif_available", True)),
                test_results_before=_opt_str_dict(args, "test_results_before"),
                test_results_after=_opt_str_dict(args, "test_results_after"),
                interface_records=_opt_dict_list(args, "interface_records"),
                run_events=_opt_dict_list(args, "run_events"),
                allowlisted_paths=_opt_str_list(args, "allowlisted_paths"),
                required_tests=_opt_str_list(args, "required_tests"),
                poc_required=bool(args.get("poc_required", False)),
                calibration_family=_opt_str(args, "calibration_family"),
                intended_behaviour_change=_opt_str(args, "intended_behaviour_change"),
                actual_files_changed=_opt_str_list(args, "actual_files_changed"),
                actual_side_effects=_opt_str_list(args, "actual_side_effects"),
                invariants_violated=_opt_str_list(args, "invariants_violated"),
                risks_materialised=_opt_str_list(args, "risks_materialised"),
                incident_ids=_opt_str_list(args, "incident_ids"),
                permission_mode=_opt_str(args, "permission_mode"),
                budget_hard_stop=bool(args.get("budget_hard_stop", False)),
                trace_complete=args.get("trace_complete"),
            )
        )
        report_payload = report.model_dump_json(indent=2)
        artifact = _store_artifact(context, report_payload, "report")
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "report": report.model_dump(mode="json"),
                "harness_condition": sheet.model_dump(mode="json"),
            },
            artifact_refs=[artifact],
        )


_CLASSIFY_PATCH_RISK_INPUT = _schema(
    {
        "diff": {"type": "string"},
        "repo": {"type": "string"},
        "snapshot_before": {"type": "string"},
        "snapshot_after": {"type": "string"},
        "sarif_run_before": {"type": "string"},
        "sarif_run_after": {"type": "string"},
        "run_id": {"type": "string"},
        "sarif_appeared": {"type": "array", "items": {"type": "object"}},
        "sarif_disappeared": {"type": "array", "items": {"type": "object"}},
        "sarif_severity_changed": {"type": "array", "items": {"type": "object"}},
        "sarif_available": {"type": "boolean"},
        "test_results_before": {"type": "object"},
        "test_results_after": {"type": "object"},
        "interface_records": {"type": "array", "items": {"type": "object"}},
        "run_events": {"type": "array", "items": {"type": "object"}},
        "allowlisted_paths": {"type": "array", "items": {"type": "string"}},
        "required_tests": {"type": "array", "items": {"type": "string"}},
        "poc_required": {"type": "boolean"},
        "calibration_family": {"type": "string"},
        "permission_mode": {"type": "string"},
        "budget_hard_stop": {"type": "boolean"},
        "trace_complete": {"type": "boolean"},
    },
    ["diff"],
)


class ClassifyPatchRiskTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="classify_patch_risk",
        description=(
            "Phase 11 patch-risk classifier entrypoint. Returns a PatchRiskResult "
            "from the deterministic policy table plus a calibrated probability "
            "when a trained classifier is available for the calibration family."
        ),
        input_schema=_CLASSIFY_PATCH_RISK_INPUT,
        output_schema={"type": "object"},
        read_only=True,
        long_running=False,
        task_support="none",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.READ,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        diff = _diff_text(args)
        result = asyncio.run(
            _classify_patch_risk(
                diff=diff,
                repo=_opt_str(args, "repo"),
                snapshot_before=_opt_str(args, "snapshot_before"),
                snapshot_after=_opt_str(args, "snapshot_after"),
                sarif_run_before=_opt_str(args, "sarif_run_before"),
                sarif_run_after=_opt_str(args, "sarif_run_after"),
                run_id=_opt_str(args, "run_id"),
                sarif_appeared=_opt_dict_list(args, "sarif_appeared"),
                sarif_disappeared=_opt_dict_list(args, "sarif_disappeared"),
                sarif_severity_changed=_opt_dict_list(args, "sarif_severity_changed"),
                sarif_available=bool(args.get("sarif_available", True)),
                test_results_before=_opt_str_dict(args, "test_results_before"),
                test_results_after=_opt_str_dict(args, "test_results_after"),
                interface_records=_opt_dict_list(args, "interface_records"),
                run_events=_opt_dict_list(args, "run_events"),
                allowlisted_paths=_opt_str_list(args, "allowlisted_paths"),
                required_tests=_opt_str_list(args, "required_tests"),
                poc_required=bool(args.get("poc_required", False)),
                calibration_family=_opt_str(args, "calibration_family"),
                permission_mode=_opt_str(args, "permission_mode"),
                budget_hard_stop=bool(args.get("budget_hard_stop", False)),
                trace_complete=args.get("trace_complete"),
            )
        )
        import json

        artifact = _store_artifact(
            context, json.dumps(result, indent=2, sort_keys=True), "risk"
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=result,
            artifact_refs=[artifact],
            diagnostics=list(result.get("diagnostics", [])),
        )
