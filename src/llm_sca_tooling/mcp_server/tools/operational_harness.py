"""Operational harness MCP tool handlers (record, drift, policy, readiness)."""

from __future__ import annotations

import uuid
from pathlib import Path

from llm_sca_tooling.governance.policy import PolicyEvaluator
from llm_sca_tooling.hardening.harness_drift import HarnessDriftChecker
from llm_sca_tooling.hardening.manifest_regression_runner import (
    ManifestRegressionRunner,
)
from llm_sca_tooling.hardening.models import DriftClassification
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.mcp_server.tools.readiness_scoring import (
    compute_readiness_snapshot,
)
from llm_sca_tooling.release.models import ReadinessAuditReport
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass, Status
from llm_sca_tooling.schemas.incidents import Incident
from llm_sca_tooling.schemas.run_records import RunEvent, RunRecord
from llm_sca_tooling.storage.errors import RunNotFoundError


def _write_perm(*, reads_only: bool = False) -> ToolPermissionDescriptor:
    return ToolPermissionDescriptor(
        required_mode=PermissionMode.SEARCH if reads_only else PermissionMode.EDIT,
        path_scope="workspace_operational_store",
        network_requirement="none",
        side_effect_class=(
            SideEffectClass.READ_ONLY if reads_only else SideEffectClass.EXECUTES_CODE
        ),
        writes_to_store=not reads_only,
        writes_to_repo=False,
        runs_subprocesses=False,
    )


# ── record_run_event ────────────────────────────────────────────────────────


class RecordRunEventTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="record_run_event",
        description=(
            "Create a new run record or append an event to an existing run. "
            "Pass 'action': 'create' with a run_record payload to open a run; "
            "pass 'action': 'append' with run_id and event payload to add an event; "
            "pass 'action': 'close' with run_id and status to close a run."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "append", "close"],
                },
                "run_record": {"type": "object"},
                "run_id": {"type": "string"},
                "event": {"type": "object"},
                "status": {"type": "string"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=False,
        permission=_write_perm(),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        action = args.get("action")
        store = context.workspace.operations

        if action == "create":
            raw = args.get("run_record")
            if not isinstance(raw, dict):
                raise ToolInvalidArguments("run_record dict is required for create")
            try:
                record = RunRecord.model_validate(raw)
            except Exception as exc:
                raise ToolInvalidArguments(f"invalid run_record: {exc}") from exc
            result = store.create_run(record)
            return ToolResult(
                tool_name=self.descriptor.name,
                status="completed",
                payload={"run": result.model_dump(mode="json")},
            )

        if action == "append":
            run_id = args.get("run_id")
            raw_event = args.get("event")
            if not isinstance(run_id, str) or not run_id:
                raise ToolInvalidArguments("run_id is required for append")
            if not isinstance(raw_event, dict):
                raise ToolInvalidArguments("event dict is required for append")
            try:
                event = RunEvent.model_validate(raw_event)
            except Exception as exc:
                raise ToolInvalidArguments(f"invalid event: {exc}") from exc
            result_event = store.append_run_event(run_id, event)
            return ToolResult(
                tool_name=self.descriptor.name,
                status="completed",
                payload={"event": result_event.model_dump(mode="json")},
            )

        if action == "close":
            run_id = args.get("run_id")
            status_str = args.get("status", "completed")
            if not isinstance(run_id, str) or not run_id:
                raise ToolInvalidArguments("run_id is required for close")
            try:
                status = Status(status_str)
            except ValueError as exc:
                raise ToolInvalidArguments(f"invalid status: {status_str}") from exc
            closed = store.close_run(run_id, status)
            return ToolResult(
                tool_name=self.descriptor.name,
                status="completed",
                payload={"run": closed.model_dump(mode="json")},
            )

        raise ToolInvalidArguments(f"unknown action: {action!r}")


# ── record_harness_condition ────────────────────────────────────────────────


class RecordHarnessConditionTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="record_harness_condition",
        description=(
            "Record a HarnessCondition sheet into the operational store. "
            "Accepts a harness_condition JSON object matching the HarnessCondition schema."
        ),
        input_schema={
            "type": "object",
            "properties": {"harness_condition": {"type": "object"}},
            "required": ["harness_condition"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=False,
        permission=_write_perm(),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        from llm_sca_tooling.schemas.harness import HarnessCondition

        raw = args.get("harness_condition")
        if not isinstance(raw, dict):
            raise ToolInvalidArguments("harness_condition dict is required")
        try:
            condition = HarnessCondition.model_validate(raw)
        except Exception as exc:
            raise ToolInvalidArguments(f"invalid harness_condition: {exc}") from exc
        stored = context.workspace.operations.record_harness_condition(condition)
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={"harness_condition": stored.model_dump(mode="json")},
        )


# ── evaluate_tool_policy ────────────────────────────────────────────────────


class EvaluateToolPolicyTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="evaluate_tool_policy",
        description=(
            "Evaluate whether a tool call is allowed under a permission profile. "
            "Returns allow / deny / approval_required."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_category": {
                    "type": "string",
                    "enum": ["read", "search", "edit", "execute", "review", "commit"],
                },
                "permission_profile": {"type": "string"},
                "requested_path": {"type": "string"},
                "network_required": {"type": "boolean"},
            },
            "required": ["tool_name", "tool_category", "permission_profile"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        tool_name = args.get("tool_name")
        tool_category = args.get("tool_category")
        permission_profile = args.get("permission_profile")
        if not isinstance(tool_name, str) or not tool_name:
            raise ToolInvalidArguments("tool_name is required")
        if not isinstance(tool_category, str) or not tool_category:
            raise ToolInvalidArguments("tool_category is required")
        if not isinstance(permission_profile, str) or not permission_profile:
            raise ToolInvalidArguments("permission_profile is required")

        evaluator = PolicyEvaluator()
        decision = evaluator.evaluate_tool_call(
            tool_name=tool_name,
            tool_category=tool_category,
            permission_profile=permission_profile,
            requested_path=args.get("requested_path") or None,
            network_required=bool(args.get("network_required", False)),
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "action": decision.action,
                "reason": decision.reason,
                "policy_id": decision.policy_id,
            },
        )


# ── detect_run_anomalies ────────────────────────────────────────────────────


class DetectRunAnomaliesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="detect_run_anomalies",
        description=(
            "Scan operational records for a run and report anomalies: "
            "policy violations, budget hard stops, and failed verification gates."
        ),
        input_schema={
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        run_id = args.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ToolInvalidArguments("run_id is required")

        store = context.workspace.operations
        try:
            view = store.get_run(run_id, include_events=True)
        except RunNotFoundError as exc:
            raise ToolInvalidArguments(str(exc)) from exc

        from llm_sca_tooling.schemas.enums import PolicyAction
        from llm_sca_tooling.schemas.run_records import RunEventType

        anomalies: list[JsonObject] = []
        for event in view.events:
            if event.type == RunEventType.BUDGET_HARD_STOP:
                anomalies.append(
                    {"type": "budget_hard_stop", "seq": event.seq, "ts": event.ts}
                )
            if event.type == RunEventType.POLICY_DECISION and event.policy_action in {
                PolicyAction.DENY,
                PolicyAction.APPROVAL_REQUIRED,
            }:
                anomalies.append(
                    {
                        "type": "policy_violation",
                        "seq": event.seq,
                        "ts": event.ts,
                        "action": (
                            event.policy_action.value if event.policy_action else None
                        ),
                    }
                )
            if event.type == RunEventType.VERIFICATION_COMPLETED:
                payload = event.payload or {}
                if not payload.get("passed", True):
                    anomalies.append(
                        {
                            "type": "verification_failed",
                            "seq": event.seq,
                            "ts": event.ts,
                        }
                    )

        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "run_id": run_id,
                "anomaly_count": len(anomalies),
                "anomalies": anomalies,
                "clean": len(anomalies) == 0,
            },
        )


# ── compare_run_traces ──────────────────────────────────────────────────────


class CompareRunTracesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="compare_run_traces",
        description=(
            "Compare two run records side by side. "
            "Returns a diff of status, event counts, policy decisions, and budget stops."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "run_id_a": {"type": "string"},
                "run_id_b": {"type": "string"},
            },
            "required": ["run_id_a", "run_id_b"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        run_id_a = args.get("run_id_a")
        run_id_b = args.get("run_id_b")
        if not isinstance(run_id_a, str) or not run_id_a:
            raise ToolInvalidArguments("run_id_a is required")
        if not isinstance(run_id_b, str) or not run_id_b:
            raise ToolInvalidArguments("run_id_b is required")

        store = context.workspace.operations
        try:
            view_a = store.get_run(run_id_a, include_events=True)
            view_b = store.get_run(run_id_b, include_events=True)
        except RunNotFoundError as exc:
            raise ToolInvalidArguments(str(exc)) from exc

        def _summary(view) -> JsonObject:  # type: ignore[no-untyped-def]
            return {
                "run_id": view.run.run_id,
                "workflow": view.run.workflow.value,
                "status": view.run.status.value,
                "event_count": view.run.run_event_count,
                "permission_profile": view.run.permission_profile,
                "start_ts": view.run.start_ts,
                "end_ts": view.run.end_ts,
            }

        summary_a = _summary(view_a)
        summary_b = _summary(view_b)
        diffs = {
            k: {"a": summary_a[k], "b": summary_b[k]}
            for k in summary_a
            if summary_a[k] != summary_b[k]
        }
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "run_a": summary_a,
                "run_b": summary_b,
                "differences": diffs,
                "identical": len(diffs) == 0,
            },
        )


# ── assess_harness_stage ────────────────────────────────────────────────────


class AssessHarnessStageTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="assess_harness_stage",
        description=(
            "Read the harness stage from .agent/harness-stage.json and run drift checks. "
            "Returns stage, detected controls, and next-stage requirements."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        import json

        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")

        root = Path(repo)
        stage_path = root / ".agent" / "harness-stage.json"
        stage_data: JsonObject = {}
        if stage_path.exists():
            try:
                stage_data = json.loads(stage_path.read_text(encoding="utf-8"))
            except Exception:
                stage_data = {}

        current_stage = str(stage_data.get("stage", "unknown"))
        checker = HarnessDriftChecker()
        drift_records = checker.check_repo(root, expected_stage=current_stage)

        clean_count = sum(
            1 for r in drift_records if r.classification == DriftClassification.CLEAN
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "repo": repo,
                "stage": current_stage,
                "stage_data": stage_data,
                "drift_check_count": len(drift_records),
                "clean_count": clean_count,
                "drift_records": [r.model_dump(mode="json") for r in drift_records],
                "all_clean": clean_count == len(drift_records),
            },
        )


# ── classify_harness_drift ──────────────────────────────────────────────────


class ClassifyHarnessDriftTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="classify_harness_drift",
        description=(
            "Run drift classification over the harness artifacts of a repository. "
            "Returns per-artifact drift classes (CLEAN, STALE, RELAXED, MISSING, OUT_OF_STAGE). "
            "RELAXED drift blocks release."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "expected_stage": {"type": "string"},
            },
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")

        expected_stage = str(args.get("expected_stage", "S3"))
        checker = HarnessDriftChecker()
        records = checker.check_repo(repo, expected_stage=expected_stage)

        has_relaxed = any(
            r.classification == DriftClassification.RELAXED for r in records
        )
        has_missing = any(
            r.classification == DriftClassification.MISSING for r in records
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "repo": repo,
                "expected_stage": expected_stage,
                "records": [r.model_dump(mode="json") for r in records],
                "blocks_release": has_relaxed,
                "has_missing": has_missing,
                "summary": {
                    cls.value: sum(1 for r in records if r.classification == cls)
                    for cls in DriftClassification
                },
            },
        )


# ── validate_harness_controls ───────────────────────────────────────────────


class ValidateHarnessControlsTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="validate_harness_controls",
        description=(
            "Check that all required harness controls (HC1–HC6 + H0–H10) are present "
            "in AGENTS.md, CI workflows, and the workspace. "
            "Returns pass/fail per control and an overall gate result."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    # HC1-HC6 are literal labels used in AGENTS.md.
    # H0-H10 harness controls are documented by concept; match their canonical keywords.
    _REQUIRED_HC = ["HC1", "HC2", "HC3", "HC4", "HC5", "HC6"]
    _H_CONCEPTS: list[tuple[str, list[str]]] = [
        (
            "H0-supply-chain-trust",
            [
                "supply-chain",
                "lockfile",
                "dependency scan",
                "uv.lock",
                "detect-secrets",
                "gitleaks",
                "secrets.baseline",
                "dependency audit",
            ],
        ),
        (
            "H1-live-observability",
            ["structured trace", "session JSONL", "telemetry", "tool calls"],
        ),
        (
            "H2-manifest-control",
            ["AGENTS.md", "runtime overlay", "CLAUDE.md", "SKILL.md"],
        ),
        (
            "H3-context-cost-budgets",
            ["context budget", "token budget", "wall-clock budget", "compaction"],
        ),
        (
            "H4-permissions-sandbox",
            ["permission profile", "path allowlist", "sandbox", "tool DAG"],
        ),
        (
            "H5-verify-before-commit",
            ["verify-before-commit", "make verify", "formatter", "linter"],
        ),
        (
            "H6-maintainability-oracles",
            ["import-linter", "maintainability", "dependency rule", "mypy"],
        ),
        (
            "H7-evaluation-harness",
            ["evaluation harness", "Harness Condition Sheet", "benchmark", "eval"],
        ),
        ("H8-diagnosis-rollback", ["incident", "rollback", "replay", "diagnosis"]),
        (
            "H9-governed-memory",
            [
                "governed.*memory",
                "Memory Governance",
                "memory schema",
                "eviction",
                "provenance",
                "durable.*policy",
                "session note",
            ],
        ),
        (
            "H10-harness-evolution",
            ["manifest regression", "harness.*evolution", "semantic mutation"],
        ),
    ]

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        import re

        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")

        root = Path(repo)
        agents_md = root / "AGENTS.md"
        agents_text = (
            agents_md.read_text(encoding="utf-8", errors="replace")
            if agents_md.exists()
            else ""
        )

        results: list[JsonObject] = []

        # HC1-HC6: literal label match
        for control in self._REQUIRED_HC:
            present = control in agents_text
            results.append(
                {
                    "control": control,
                    "present": present,
                    "source": "AGENTS.md",
                    "match_type": "label",
                }
            )

        # H0-H10: concept-keyword match (any one keyword per control suffices)
        for control_id, keywords in self._H_CONCEPTS:
            present = any(re.search(kw, agents_text, re.IGNORECASE) for kw in keywords)
            results.append(
                {
                    "control": control_id,
                    "present": present,
                    "source": "AGENTS.md",
                    "match_type": "concept",
                }
            )

        all_pass = all(r["present"] for r in results)
        missing = [r["control"] for r in results if not r["present"]]
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "repo": repo,
                "gate_passed": all_pass,
                "missing_controls": missing,
                "control_results": results,
            },
        )


# ── compute_readiness_score ─────────────────────────────────────────────────


class ComputeReadinessScoreTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="compute_readiness_score",
        description=(
            "Compute the AI-readiness score for a repository by inspecting harness artifacts, "
            "CI configuration, documentation, and security controls. "
            "Returns a score (0-25) across five axes."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")

        snapshot = compute_readiness_snapshot(repo)
        report = ReadinessAuditReport(
            report_id=f"readiness:{uuid.uuid4().hex}",
            repo_id=repo,
            ai_readiness_score=snapshot.total_score,
            harness_stage=snapshot.harness_stage,
            drift_findings=snapshot.drift_findings,
            missing_gates=snapshot.missing_gates,
            absent_scanners=snapshot.absent_scanners,
            recommended_readiness_tasks=snapshot.recommended_tasks,
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "report": report.model_dump(mode="json"),
                "axis_scores": snapshot.axis_scores,
            },
        )


# ── run_maintainability_oracles ─────────────────────────────────────────────


class RunMaintainabilityOraclesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_maintainability_oracles",
        description=(
            "Run maintainability oracle checks against the repository: "
            "import-linter, mypy type coverage, and ruff lint. "
            "Returns pass/fail per oracle and an overall gate result."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=False,
            writes_to_repo=False,
            runs_subprocesses=True,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        import subprocess

        repo = args.get("repo")
        if not isinstance(repo, str) or not repo:
            raise ToolInvalidArguments("repo is required")

        results: list[JsonObject] = []

        def _run(name: str, cmd: list[str]) -> JsonObject:
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                return {
                    "oracle": name,
                    "passed": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[:2000],
                    "stderr": proc.stderr[:500],
                }
            except Exception as exc:
                return {"oracle": name, "passed": False, "error": str(exc)}

        results.append(_run("ruff", ["uv", "run", "ruff", "check", "src", "tests"]))
        results.append(_run("mypy", ["uv", "run", "mypy", "src"]))
        results.append(_run("import-linter", ["uv", "run", "lint-imports"]))

        gate_passed = all(r.get("passed", False) for r in results)
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "repo": repo,
                "gate_passed": gate_passed,
                "oracle_results": results,
            },
        )


# ── run_prompt_manifest_regression ─────────────────────────────────────────


class RunPromptManifestRegressionTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_prompt_manifest_regression",
        description=(
            "Compare two manifest snapshots (baseline vs current) and report "
            "breaking changes. A breaking change blocks release."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "baseline": {"type": "object"},
                "current": {"type": "object"},
            },
            "required": ["baseline", "current"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=True,
        permission=_write_perm(reads_only=True),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        baseline = args.get("baseline")
        current = args.get("current")
        if not isinstance(baseline, dict):
            raise ToolInvalidArguments("baseline must be an object")
        if not isinstance(current, dict):
            raise ToolInvalidArguments("current must be an object")

        runner = ManifestRegressionRunner()
        result = runner.compare(baseline, current)
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=result,
        )


# ── record_incident ─────────────────────────────────────────────────────────


class RecordIncidentTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="record_incident",
        description=(
            "Record an operational incident into the store. "
            "Accepts an incident JSON object matching the Incident schema."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "incident": {"type": "object"},
                "primary_repo_id": {"type": "string"},
            },
            "required": ["incident"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        read_only=False,
        permission=_write_perm(),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        raw = args.get("incident")
        if not isinstance(raw, dict):
            raise ToolInvalidArguments("incident dict is required")
        try:
            incident = Incident.model_validate(raw)
        except Exception as exc:
            raise ToolInvalidArguments(f"invalid incident: {exc}") from exc

        repo_id = args.get("primary_repo_id")
        stored = context.workspace.operations.record_incident(
            incident,
            primary_repo_id=repo_id if isinstance(repo_id, str) else None,
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={"incident": stored.model_dump(mode="json")},
        )


__all__ = [
    "AssessHarnessStageTool",
    "ClassifyHarnessDriftTool",
    "CompareRunTracesTool",
    "ComputeReadinessScoreTool",
    "DetectRunAnomaliesTool",
    "EvaluateToolPolicyTool",
    "RecordHarnessConditionTool",
    "RecordIncidentTool",
    "RecordRunEventTool",
    "RunMaintainabilityOraclesTool",
    "RunPromptManifestRegressionTool",
    "ValidateHarnessControlsTool",
]
