"""Harness Condition Sheet writer skeleton."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson


class DriftClass(str):
    MISSING = "missing"
    STALE = "stale"
    RELAXED = "relaxed"
    OUT_OF_STAGE = "out-of-stage"
    CLEAN = "clean"


class DriftClassifier:
    """Classify harness condition sheet drift relative to a reference state."""

    SEVERITY_ORDER = [
        DriftClass.MISSING,
        DriftClass.RELAXED,
        DriftClass.STALE,
        DriftClass.OUT_OF_STAGE,
        DriftClass.CLEAN,
    ]

    def classify(
        self,
        *,
        sheet: dict[str, Any],
        reference_phase: str,
        expected_gates: list[str],
        expected_permission_profile: str,
    ) -> dict[str, Any]:
        """Return a drift classification dict with class, reasons, and severity."""
        reasons: list[str] = []
        drift_class = DriftClass.CLEAN

        if not sheet.get("run_id"):
            reasons.append("run_id missing from condition sheet")
            drift_class = DriftClass.MISSING
        if not sheet.get("phase"):
            reasons.append("phase field missing")
            drift_class = DriftClass.MISSING

        if sheet.get("phase") and sheet["phase"] != reference_phase:
            reasons.append(
                f"phase mismatch: expected {reference_phase!r}, got {sheet['phase']!r}"
            )
            if drift_class == DriftClass.CLEAN:
                drift_class = DriftClass.OUT_OF_STAGE

        gates_disabled = sheet.get("verification_gates", {}).get("gates_disabled", [])
        for gate in expected_gates:
            if gate in gates_disabled:
                reasons.append(f"gate {gate!r} is disabled (expected enabled)")
                if drift_class in (
                    DriftClass.CLEAN,
                    DriftClass.STALE,
                    DriftClass.OUT_OF_STAGE,
                ):
                    drift_class = DriftClass.RELAXED

        actual_profile = sheet.get("permission_mode", {}).get("permission_profile", "")
        if actual_profile and actual_profile != expected_permission_profile:
            reasons.append(
                f"permission profile mismatch: expected"
                f" {expected_permission_profile!r}, got {actual_profile!r}"
            )
            if drift_class == DriftClass.CLEAN:
                drift_class = DriftClass.STALE

        return {
            "drift_class": drift_class,
            "reasons": reasons,
            "clean": drift_class == DriftClass.CLEAN,
        }


class HarnessConditionWriter:
    def __init__(self, output_dir: Path | str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir is not None else None

    def capture(
        self,
        run_id: str,
        phase: str,
        runtime_version: str,
        model_backend: str,
        toolset_hash: str,
        permission_profile: str,
        context_budget: int | None,
        gates_enabled: list[str],
        gates_disabled: list[str],
        trace_location: str | None,
        trace_completeness: str,
        redaction_policy: str,
    ) -> dict[str, Any]:
        """Return a Harness Condition Sheet dict and optionally persist it."""

        sheet = {
            "run_id": run_id,
            "report_date": datetime.now(UTC).date().isoformat(),
            "phase": phase,
            "runtime_and_model": {
                "runtime_version": runtime_version,
                "model_backend": model_backend,
                "mcp_server_version": runtime_version,
            },
            "manifest_state": {
                "agents_revision": "current-worktree",
                "active_runtime_overlays": [
                    "CLAUDE.md",
                    ".codex/INSTRUCTIONS.md",
                    ".github/copilot-instructions.md",
                ],
                "skill_templates_active": True,
            },
            "exposed_tools": {
                "toolset_hash": toolset_hash,
                "tools_active": [],
                "tools_disabled_or_unavailable": [],
            },
            "permission_mode": {
                "permission_profile": permission_profile,
                "path_allowlist": "see AGENTS.md",
                "network_policy": "deny-by-default",
                "sandbox_or_devcontainer": ".devcontainer/devcontainer.json",
            },
            "verification_gates": {
                "verify_command_used": "make verify",
                "gates_enabled": gates_enabled,
                "gates_disabled": gates_disabled,
            },
            "context_and_cost_policy": {
                "context_budget": context_budget,
                "token_budget": context_budget,
                "retry_budget": 3,
                "wall_clock_budget_seconds": 3600,
                "compaction_policy": "compact at runtime-specific threshold",
            },
            "telemetry": {
                "session_trace_location": trace_location,
                "trace_completeness": trace_completeness,
                "redaction_policy_applied": redaction_policy,
            },
            "evaluation_notes": {
                "known_limitations": [],
                "deviations_from_standard_harness": [],
                "waived_controls": [],
            },
        }
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (
                self.output_dir / f"{run_id.replace(':', '_')}.harness-condition.json"
            ).write_text(
                orjson.dumps(
                    sheet,
                    option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
                ).decode("utf-8")
                + "\n",
                encoding="utf-8",
            )
        return sheet
