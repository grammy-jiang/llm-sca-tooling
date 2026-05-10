"""Phase 10 evaluation MCP tools."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.artefact_writer import EvaluationArtifactWriter
from llm_sca_tooling.evaluation.contamination import unknown_contamination_canary
from llm_sca_tooling.evaluation.harness_condition import (
    default_harness_condition_sheet,
)
from llm_sca_tooling.evaluation.models import (
    EvalRun,
    EvalStatus,
    FreshnessRecord,
    utc_now_ts,
)
from llm_sca_tooling.evaluation.rds_features import compute_rds_features
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.store import EvalRunStore
from llm_sca_tooling.evaluation.t1_runner import T1SmokeRunner
from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.notifications import NotificationManager
from llm_sca_tooling.mcp_server.task_runner import TaskRunner
from llm_sca_tooling.mcp_server.task_store import TaskRecord
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.schemas.enums import PermissionMode, SideEffectClass


def _schema(properties: JsonObject, required: list[str] | None = None) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _descriptor(
    name: str,
    description: str,
    input_schema: JsonObject,
    *,
    read_only: bool,
    long_running: bool = False,
    task_support: str = "none",
    notifications: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema={"type": "object"},
        read_only=read_only,
        long_running=long_running,
        task_support=task_support,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=not read_only,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
        emits_resource_notifications=notifications,
    )


class ComputeRdsFeaturesTool(ToolHandler):
    descriptor = _descriptor(
        "compute_rds_features",
        "Compute an RDS v0.2 feature vector for a local smoke eval instance.",
        _schema(
            {
                "instance_id": {"type": "string"},
                "eval_run_id": {"type": "string"},
                "suite_root": {"type": "string"},
            },
            ["instance_id"],
        ),
        read_only=False,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        instance_id = _required_str(args, "instance_id")
        eval_run_id = str(args.get("eval_run_id") or "eval:ad-hoc-rds")
        adapter = _smoke_adapter(args.get("suite_root"))
        try:
            descriptor = next(
                item
                for item in adapter.list_instances()
                if item.instance_id == instance_id
            )
        except StopIteration as exc:
            raise ToolInvalidArguments(
                f"unknown smoke instance: {instance_id}"
            ) from exc
        issue = adapter.load_issue(instance_id)
        gold_patch = adapter.load_gold_patch(instance_id)
        vector = compute_rds_features(
            eval_run_id=eval_run_id,
            descriptor=descriptor,
            issue=issue,
            gold_patch=gold_patch,
            conn=context.workspace.conn,
        )
        ref = EvaluationArtifactWriter(context.workspace).write_json(
            eval_run_id,
            f"rds_{instance_id}",
            vector.model_dump(mode="json"),
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "rds_features": vector.model_dump(mode="json"),
                "artifact_ref": ref.model_dump(mode="json"),
            },
            artifact_refs=[ref],
            diagnostics=[
                {"axis": axis, "message": message}
                for axis, message in vector.diagnostics.items()
            ],
        )


class RecordEvalResultTool(ToolHandler):
    def __init__(self, notifications: NotificationManager) -> None:
        self.notifications = notifications

    descriptor = _descriptor(
        "record_eval_result",
        "Validate, persist, and publish an evaluation run record.",
        _schema({"eval_run": {"type": "object"}}, ["eval_run"]),
        read_only=False,
        notifications=True,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        payload = args.get("eval_run")
        if not isinstance(payload, dict):
            raise ToolInvalidArguments("eval_run is required")
        run = EvalRun.model_validate(payload)
        if not run.harness_condition:
            raise ToolInvalidArguments("eval_run.harness_condition is required")
        if run.aggregate_metrics is None:
            raise ToolInvalidArguments("eval_run.aggregate_metrics is required")
        run = EvaluationArtifactWriter(context.workspace).write_eval_run_bundle(run)
        stored = EvalRunStore(context.workspace.conn).record_eval_run(run)
        uri = f"code-intelligence://eval/{stored.eval_run_id}"
        notification = self.notifications.resources_updated(
            uri, payload={"eval_run_id": stored.eval_run_id}
        )
        warnings = []
        if (
            stored.freshness_record
            and stored.freshness_record.median_age_days
            and stored.freshness_record.median_age_days > 30
        ):
            warnings.append("suite_median_age_gt_30_days")
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload={
                "eval_run_id": stored.eval_run_id,
                "resource_uri": uri,
                "warnings": warnings,
            },
            notifications=[item.model_dump(mode="json") for item in notification],
        )


class RunEvalSuiteTool(ToolHandler):
    def __init__(
        self, task_runner: TaskRunner, notifications: NotificationManager
    ) -> None:
        self.task_runner = task_runner
        self.notifications = notifications

    descriptor = _descriptor(
        "run_eval_suite",
        "Launch a Phase 10 T1 smoke/null evaluation suite as a persisted task.",
        _schema(
            {
                "suite": {"type": "string"},
                "instance_ids": {"type": "array", "items": {"type": "string"}},
                "model_backend": {"type": "string"},
                "policy_id": {"type": "string"},
                "permission_profile": {"type": "string"},
                "null_mode": {"type": "boolean"},
                "suite_root": {"type": "string"},
            }
        ),
        read_only=False,
        long_running=True,
        task_support="required",
        notifications=True,
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        suite = str(args.get("suite") or "smoke")

        def executor(record: TaskRecord) -> JsonObject:
            if suite not in {"smoke", "t1"}:
                run = _not_implemented_eval_run(
                    suite=suite,
                    model_backend=str(args.get("model_backend") or "null"),
                    permission_profile=str(
                        args.get("permission_profile") or "scoped-execute"
                    ),
                    context=context,
                )
            else:
                adapter = _smoke_adapter(args.get("suite_root"))
                runner = T1SmokeRunner(adapter, context.workspace)
                run = runner.run(
                    instance_ids=_string_list(args.get("instance_ids")),
                    model_backend=str(args.get("model_backend") or "null"),
                    policy_id=str(args.get("policy_id") or "policy:phase10-null"),
                    permission_profile=str(
                        args.get("permission_profile") or "scoped-execute"
                    ),
                    null_mode=bool(args.get("null_mode", True)),
                )
            uri = f"code-intelligence://eval/{run.eval_run_id}"
            self.notifications.resources_updated(
                uri, payload={"task_id": record.task_id, "eval_run_id": run.eval_run_id}
            )
            return {
                "run_id": run.eval_run_id,
                "eval_run_id": run.eval_run_id,
                "eval_resource": uri,
                "eval_run": run.model_dump(mode="json"),
                "resource_updates": [uri],
            }

        task = self.task_runner.start(
            self.descriptor.name,
            args,
            executor,
            authorization_context_hash=context.authorization_context_hash,
            metadata={"suite": suite},
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="task_created",
            payload={"task": task.model_dump(mode="json")},
            artifact_refs=(
                [task.result_artifact_ref] if task.result_artifact_ref else []
            ),
            notifications=[
                notification.model_dump(mode="json")
                for notification in self.notifications.all()
            ],
        )


def _not_implemented_eval_run(
    *,
    suite: str,
    model_backend: str,
    permission_profile: str,
    context: McpRequestContext,
) -> EvalRun:
    eval_run_id = f"eval:not-implemented:{suite}:{utc_now_ts()}"
    hcs = default_harness_condition_sheet(
        run_id=eval_run_id,
        model_backend=model_backend,
        tool_set=["run_eval_suite"],
        permission_mode=permission_profile,
    )
    freshness = FreshnessRecord(
        suite_id=suite,
        suite_version="phase10-skeleton",
        median_age_days=None,
        freshness_check_ts=utc_now_ts(),
    )
    run = EvalRun(
        eval_run_id=eval_run_id,
        suite_id=suite,
        suite_version="phase10-skeleton",
        suite_median_age_days=None,
        target_workflow="evaluation",
        target_tool="run_eval_suite",
        model_backend=model_backend,
        toolset_hash=hcs.tool_set_hash,
        policy_id="policy:phase10-null",
        permission_profile=permission_profile,
        harness_condition_id=hcs.hcs_id,
        start_ts=utc_now_ts(),
        end_ts=utc_now_ts(),
        status=EvalStatus.PARTIAL,
        instance_count=0,
        contamination_canary_result=unknown_contamination_canary(
            eval_run_id=eval_run_id, model_id=model_backend
        ),
        freshness_check_ts=freshness.freshness_check_ts,
        notes=[f"{suite} is not implemented until a later phase."],
        freshness_record=freshness,
        harness_condition=hcs.model_dump(mode="json"),
    )
    run = EvaluationArtifactWriter(context.workspace).write_eval_run_bundle(run)
    EvalRunStore(context.workspace.conn).record_eval_run(run)
    return run


def _required_str(args: JsonObject, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInvalidArguments(f"{key} is required")
    return value


def _string_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolInvalidArguments("instance_ids must be a list of strings")
    return [str(item) for item in value]


def _smoke_adapter(suite_root: object) -> LocalSmokeAdapter:
    if suite_root is None:
        return LocalSmokeAdapter()
    if not isinstance(suite_root, str):
        raise ToolInvalidArguments("suite_root must be a string")
    return LocalSmokeAdapter(Path(suite_root))
