"""Phase 4 MCP tool handlers."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from llm_sca_tooling.evaluation.artefact_writer import EvalStore
from llm_sca_tooling.evaluation.benchmark_adapter import GoldPatchRecord
from llm_sca_tooling.evaluation.models import EvalRun
from llm_sca_tooling.evaluation.rds_features import compute_rds_features
from llm_sca_tooling.evaluation.smoke_adapter import LocalSmokeAdapter
from llm_sca_tooling.evaluation.t1_runner import run_t1_null
from llm_sca_tooling.evaluation.t3_runner import run_t3_null
from llm_sca_tooling.evaluation.t4_runner import run_t4_null
from llm_sca_tooling.fl.localisation import get_relevant_files
from llm_sca_tooling.impl_check.report import run_implementation_check
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.resource_uris import validate_relative_path
from llm_sca_tooling.mcp_server.tasks import TaskManager, TaskRecord
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolResult,
)
from llm_sca_tooling.memory.eviction.compactor import compact
from llm_sca_tooling.memory.models import (
    EvictionPolicy,
    OperationalLesson,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.policy import MemoryDisabledError
from llm_sca_tooling.memory.promotion.pipeline import (
    UnreviewedLessonError,
    promote_lesson,
)
from llm_sca_tooling.memory.retrieval.coarse import retrieve_coarse
from llm_sca_tooling.memory.retrieval.fine import retrieve_fine
from llm_sca_tooling.memory.write_path import validate_and_write
from llm_sca_tooling.patch_review.report import run_patch_review
from llm_sca_tooling.patch_review.risk_classifier import classify_patch_risk
from llm_sca_tooling.patch_review.sampling_integration import sampling_supported
from llm_sca_tooling.plugins.base import TraversalDirection
from llm_sca_tooling.plugins.registry import build_default_registry
from llm_sca_tooling.plugins.service import reload_plugins
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.plugins.traversal import CrossLanguageTraverser
from llm_sca_tooling.qa.blame import BlameResource
from llm_sca_tooling.qa.classifier import classify_question
from llm_sca_tooling.qa.interface_lookup import lookup_interface_contract
from llm_sca_tooling.qa.question import normalize_question
from llm_sca_tooling.qa.service import (
    answer_repo_question as answer_repo_question_service,
)
from llm_sca_tooling.release.operational_review import (
    run_operational_review as build_operational_review,
)
from llm_sca_tooling.release.readiness_audit import (
    run_readiness_audit as build_readiness_audit,
)
from llm_sca_tooling.sarif.service import run_static_analysis
from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.report import run_sast_repair
from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules
from llm_sca_tooling.storage.graph_queries import GraphSlice
from llm_sca_tooling.traces.service import capture_trace
from llm_sca_tooling.workflows.bug_resolve.report import run_issue_resolution

__all__ = ["CoreToolHandlers", "register_core_tools"]


def _object_schema(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required or [],
    }


def _result_to_payload(result: Any) -> dict[str, Any]:
    payload = asdict(result)
    payload["diagnostics"] = [d.to_dict() for d in result.diagnostics]
    return payload


def _slice_payload(graph_slice: GraphSlice) -> dict[str, Any]:
    return {
        "repo_id": graph_slice.repo_id,
        "requested_snapshot_id": graph_slice.requested_snapshot_id,
        "snapshot_ids": graph_slice.snapshot_ids,
        "snapshot_consistency": graph_slice.snapshot_consistency,
        "nodes": [n.model_dump(mode="json") for n in graph_slice.nodes],
        "edges": [e.model_dump(mode="json") for e in graph_slice.edges],
        "diagnostics": graph_slice.diagnostics,
        "truncated": graph_slice.truncated,
        "limit": graph_slice.limit,
        "provenance_summary": graph_slice.provenance_summary,
    }


class CoreToolHandlers:
    def __init__(self, context: McpServerContext, tasks: TaskManager) -> None:
        self._context = context
        self._tasks = tasks
        self._plugins = build_default_registry()
        self._eval_store = EvalStore(
            self._context.config.workspace_path / ".llm-sca" / "eval.sqlite"
        )
        self._memory_store = context.memory

    async def register_repo(self, args: dict[str, Any]) -> ToolResult:
        path_arg = args.get("repo_path")
        if not isinstance(path_arg, str):
            raise ToolInvalidArguments("register_repo requires repo_path")
        path = Path(path_arg)
        if not path.exists() or not path.is_dir():
            raise ToolInvalidArguments("repo_path must be an existing directory")
        record = await self._context.workspace.registry.register_repo(
            path, name=args.get("name") if isinstance(args.get("name"), str) else None
        )
        note = self._context.notifications.emit_list_changed()
        self._context.telemetry.record_tool_call("register_repo", args, "completed")
        return ToolResult(
            tool_name="register_repo",
            status="completed",
            payload={"repo": record.redacted()},
            notifications=[note.to_dict()],
        )

    async def get_graph_slice(self, args: dict[str, Any]) -> ToolResult:
        repo_id = _required_str(args, "repo")
        files_arg = args.get("files", [])
        if not isinstance(files_arg, list) or not all(
            isinstance(f, str) for f in files_arg
        ):
            raise ToolInvalidArguments("files must be a list of repo-relative paths")
        files = [validate_relative_path(f, for_tool=True) for f in files_arg]
        await self._context.workspace.registry.get_repo(repo_id)
        if not files:
            payload: dict[str, Any] = {
                "repo_id": repo_id,
                "nodes": [],
                "edges": [],
                "diagnostics": [],
                "snapshot_ids": [],
                "snapshot_consistency": "unknown",
                "truncated": False,
            }
        else:
            generator = GraphSliceGenerator(
                self._context.workspace.queries,
                IndexingConfig(
                    graph_slice_limit=self._context.config.max_graph_slice_nodes
                ),
            )
            slices = [await generator.slice_by_file(repo_id, file) for file in files]
            payload = _slice_payload(slices[0])
            if len(slices) > 1:
                payload["nodes"] = [
                    node for item in slices for node in _slice_payload(item)["nodes"]
                ]
                payload["edges"] = [
                    edge for item in slices for edge in _slice_payload(item)["edges"]
                ]
                payload["snapshot_ids"] = sorted(
                    {sid for item in slices for sid in item.snapshot_ids}
                )
                payload["snapshot_consistency"] = (
                    "mixed" if len(payload["snapshot_ids"]) > 1 else "clean"
                )
        self._context.telemetry.record_tool_call("get_graph_slice", args, "completed")
        return ToolResult(
            tool_name="get_graph_slice",
            status="completed",
            payload=payload,
            diagnostics=payload.get("diagnostics", []),
        )

    async def find_callers(self, args: dict[str, Any]) -> ToolResult:
        return await self._call_graph_query(
            args, direction="in", tool_name="find_callers"
        )

    async def find_callees(self, args: dict[str, Any]) -> ToolResult:
        return await self._call_graph_query(
            args, direction="out", tool_name="find_callees"
        )

    async def _call_graph_query(
        self, args: dict[str, Any], *, direction: str, tool_name: str
    ) -> ToolResult:
        repo_id = args.get("repo")
        symbol = _required_str(args, "symbol")
        depth = int(args.get("depth", 1))
        include_cross_repo = bool(args.get("include_cross_repo", False))
        include_cross_language = bool(args.get("include_cross_language", False))
        if include_cross_repo:
            diagnostics = [
                {
                    "code": "CROSS_REPO_UNAVAILABLE",
                    "message": "cross-repo traversal is not implemented in Phase 4",
                }
            ]
        else:
            diagnostics = []
        node_ids = await self._find_symbol_nodes(
            repo_id if isinstance(repo_id, str) else None, symbol
        )
        if not node_ids:
            diagnostics.append(
                {"code": "SYMBOL_NOT_FOUND", "message": "symbol not found"}
            )
            payload: dict[str, Any] = {
                "nodes": [],
                "edges": [],
                "diagnostics": diagnostics,
            }
        else:
            graph_slice = await self._fetch_calls(
                node_ids, direction=direction, depth=depth
            )
            payload = _slice_payload(graph_slice)
            payload["diagnostics"] = [*payload.get("diagnostics", []), *diagnostics]
            if include_cross_language:
                traversal = await CrossLanguageTraverser(
                    self._plugins, self._context.workspace
                ).traverse(node_ids[0], max_hops=max(depth, 2))
                payload["cross_language_hops"] = [
                    hop.model_dump(mode="json") for hop in traversal.hops
                ]
                payload["cross_language_node_ids"] = traversal.reached_node_ids
                payload["diagnostics"].extend(
                    {"message": item} for item in traversal.diagnostics
                )
        self._context.telemetry.record_tool_call(tool_name, args, "completed")
        return ToolResult(
            tool_name=tool_name,
            status="completed",
            payload=payload,
            diagnostics=diagnostics,
        )

    async def git_blame_chain(self, args: dict[str, Any]) -> ToolResult:
        repo_id = _required_str(args, "repo")
        file_path = validate_relative_path(_required_str(args, "file"), for_tool=True)
        repo = await self._context.workspace.registry.get_repo(repo_id)
        line = _optional_int(args, "line")
        start_line = _optional_int(args, "start_line")
        end_line = _optional_int(args, "end_line")
        blame = BlameResource.from_git(
            repo.root_path,
            repo_id,
            file_path,
            line=line,
            start_line=start_line,
            end_line=end_line,
        )
        artifacts = await self._context.workspace.artifacts.list_artifacts(
            repo_id=repo_id, kind="blame", limit=100
        )
        matching = [a for a in artifacts if file_path in a["uri"]]
        diagnostics = (
            []
            if matching
            else [
                {"code": "BLAME_CACHE_MISS", "message": "No blame-chain artifact found"}
            ]
        )
        self._context.telemetry.record_tool_call("git_blame_chain", args, "completed")
        return ToolResult(
            tool_name="git_blame_chain",
            status="completed",
            payload={
                "repo_id": repo_id,
                "file_path": file_path,
                "entries": [entry.model_dump(mode="json") for entry in blame.entries],
                "artifact_refs": matching,
            },
            artifact_refs=matching,
            diagnostics=[*diagnostics, *[{"message": d} for d in blame.diagnostics]],
        )

    async def classify_repo_question(self, args: dict[str, Any]) -> ToolResult:
        question = _required_str(args, "question")
        repos_arg = args.get("repos")
        repos = (
            [str(item) for item in repos_arg] if isinstance(repos_arg, list) else None
        )
        repo_question = normalize_question(question, repos=repos)
        result = classify_question(
            repo_question, use_llm_fallback=bool(args.get("use_llm_fallback", False))
        )
        return ToolResult(
            tool_name="classify_repo_question",
            status="completed",
            payload={**result.model_dump(mode="json"), "run_event_ids": []},
        )

    async def answer_repo_question(self, args: dict[str, Any]) -> ToolResult:
        question = _required_str(args, "question")
        repos_arg = args.get("repos")
        repos = (
            [str(item) for item in repos_arg] if isinstance(repos_arg, list) else None
        )
        answer = await answer_repo_question_service(
            self._context.workspace,
            self._context.workspace.queries,
            question=question,
            repos=repos,
            question_class_hint=(
                args.get("question_class_hint")
                if isinstance(args.get("question_class_hint"), str)
                else None
            ),
            synthesis=bool(args.get("synthesis", True)),
            synthesis_mode=(
                args.get("synthesis_mode")
                if isinstance(args.get("synthesis_mode"), str)
                else None
            ),
            max_evidence=int(args.get("max_evidence", 20)),
            max_hops=int(args.get("max_hops", 8)),
            snapshot=(
                args.get("snapshot") if isinstance(args.get("snapshot"), str) else None
            ),
            registry=self._plugins,
            interface_store=InterfaceRecordStore(self._context.workspace),
        )
        return ToolResult(
            tool_name="answer_repo_question",
            status="completed",
            payload=answer.model_dump(mode="json"),
            diagnostics=[{"message": answer.uncertainty}] if answer.uncertainty else [],
        )

    async def get_interface_contract(self, args: dict[str, Any]) -> ToolResult:
        result = await lookup_interface_contract(
            InterfaceRecordStore(self._context.workspace),
            self._context.workspace.queries,
            plugin_id=_required_str(args, "plugin_id"),
            interface_name=_required_str(args, "interface_name"),
            repo=args.get("repo") if isinstance(args.get("repo"), str) else None,
            include_operations=bool(args.get("include_operations", True)),
            include_node_refs=bool(args.get("include_node_refs", True)),
        )
        if result is None:
            return ToolResult(
                tool_name="get_interface_contract",
                status="not_found",
                payload={"interface_record": None, "run_event_ids": []},
                diagnostics=[
                    {"code": "ResourceNotFound", "message": "interface not found"}
                ],
            )
        payload = result.model_dump(mode="json")
        payload["run_event_ids"] = []
        return ToolResult(
            tool_name="get_interface_contract",
            status="completed",
            payload=payload,
        )

    async def get_relevant_files(self, args: dict[str, Any]) -> ToolResult:
        issue_text = _required_str(args, "issue_text")
        repos_arg = args.get("repos")
        repos = (
            [str(item) for item in repos_arg] if isinstance(repos_arg, list) else None
        )
        result, context = await get_relevant_files(
            self._context.workspace,
            issue_text=issue_text,
            repos=repos,
            failing_tests=(
                [str(item) for item in args.get("failing_tests", [])]
                if isinstance(args.get("failing_tests"), list)
                else None
            ),
            coverage_path=(
                args.get("coverage_path")
                if isinstance(args.get("coverage_path"), str)
                else None
            ),
            max_files=int(args.get("max_files", 8)),
            include_symbols=bool(args.get("include_symbols", False)),
            snapshot=(
                args.get("snapshot") if isinstance(args.get("snapshot"), str) else None
            ),
            use_embedding=bool(args.get("use_embedding", True)),
        )
        payload = result.model_dump(mode="json")
        payload["context_bundle"] = context.model_dump(mode="json")
        return ToolResult(
            tool_name="get_relevant_files",
            status="completed",
            payload=payload,
            diagnostics=[{"message": result.uncertainty}] if result.uncertainty else [],
        )

    async def compute_rds_features(self, args: dict[str, Any]) -> ToolResult:
        instance_id = _required_str(args, "instance_id")
        patch_ref = args.get("gold_patch_ref")
        gold_patch = None
        if isinstance(patch_ref, str) and patch_ref:
            patch_path = Path(patch_ref)
            if patch_path.exists() and patch_path.is_file():
                gold_patch = GoldPatchRecord(
                    instance_id=instance_id,
                    diff=patch_path.read_text(encoding="utf-8"),
                    changed_files=[],
                )
        vector = compute_rds_features(
            instance_id=instance_id,
            eval_run_id=str(args.get("eval_run_id") or "adhoc"),
            gold_patch=gold_patch,
            source_snapshot_id=(
                args.get("snapshot") if isinstance(args.get("snapshot"), str) else None
            ),
        )
        self._context.telemetry.record_tool_call(
            "compute_rds_features", args, "completed"
        )
        return ToolResult(
            tool_name="compute_rds_features",
            status="completed",
            payload=vector.model_dump(mode="json"),
            diagnostics=[{"message": value} for value in vector.diagnostics.values()],
        )

    async def record_eval_result(self, args: dict[str, Any]) -> ToolResult:
        payload = args.get("eval_run")
        if not isinstance(payload, dict):
            raise ToolInvalidArguments("record_eval_result requires eval_run")
        eval_run = EvalRun.model_validate(payload)
        self._eval_store.record_eval_run(eval_run)
        note = self._context.notifications.emit_updated(
            f"code-intelligence://eval/{eval_run.eval_run_id}",
            {"eval_run_id": eval_run.eval_run_id, "status": eval_run.status.value},
        )
        self._context.telemetry.record_tool_call(
            "record_eval_result", args, "completed"
        )
        return ToolResult(
            tool_name="record_eval_result",
            status="completed",
            payload=eval_run.model_dump(mode="json"),
            notifications=[note.to_dict()],
        )

    async def run_eval_suite(self, args: dict[str, Any]) -> ToolResult:
        suite = str(args.get("suite") or "smoke").lower()
        if suite in {"t3", "t4"}:
            runner = run_t3_null if suite == "t3" else run_t4_null
            eval_run = runner(
                store=self._eval_store,
                model_backend=str(args.get("model_backend") or "null"),
            )
            note = self._context.notifications.emit_updated(
                f"code-intelligence://eval/{eval_run.eval_run_id}",
                {"eval_run_id": eval_run.eval_run_id},
            )
            self._context.telemetry.record_tool_call(
                "run_eval_suite", args, "completed"
            )
            return ToolResult(
                tool_name="run_eval_suite",
                status="completed",
                payload={
                    "eval_run_ref": f"code-intelligence://eval/{eval_run.eval_run_id}",
                    "eval_run": eval_run.model_dump(mode="json"),
                },
                notifications=[note.to_dict()],
            )
        if suite not in {"t1", "smoke"}:
            raise ToolInvalidArguments("suite must be one of: t1, smoke, t3, t4")
        fixture_root = Path(
            str(
                args.get("fixture_root")
                or Path.cwd() / "tests" / "evaluation" / "fixtures" / "smoke"
            )
        )
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_eval_suite",
                args,
                lambda record: self._run_eval_suite_task(record, fixture_root),
                metadata={"suite": suite},
            )
            return ToolResult(
                tool_name="run_eval_suite",
                status="queued",
                payload={"task": task.model_dump(mode="json")},
            )
        eval_run = run_t1_null(
            adapter=LocalSmokeAdapter(fixture_root),
            store=self._eval_store,
            model_backend=str(args.get("model_backend") or "null"),
            instance_ids=(
                [str(item) for item in args.get("instance_ids", [])]
                if isinstance(args.get("instance_ids"), list)
                else None
            ),
        )
        note = self._context.notifications.emit_updated(
            f"code-intelligence://eval/{eval_run.eval_run_id}",
            {"eval_run_id": eval_run.eval_run_id},
        )
        self._context.telemetry.record_tool_call("run_eval_suite", args, "completed")
        return ToolResult(
            tool_name="run_eval_suite",
            status="completed",
            payload={
                "eval_run_ref": f"code-intelligence://eval/{eval_run.eval_run_id}",
                "eval_run": eval_run.model_dump(mode="json"),
            },
            notifications=[note.to_dict()],
        )

    async def _run_eval_suite_task(
        self, task: TaskRecord, fixture_root: Path
    ) -> dict[str, Any]:
        self._tasks.update_progress(task.task_id, "running-t1-null", percent=50)
        eval_run = run_t1_null(
            adapter=LocalSmokeAdapter(fixture_root), store=self._eval_store
        )
        self._context.notifications.emit_updated(
            f"code-intelligence://eval/{eval_run.eval_run_id}",
            {"eval_run_id": eval_run.eval_run_id},
        )
        return {
            "eval_run_ref": f"code-intelligence://eval/{eval_run.eval_run_id}",
            "eval_run": eval_run.model_dump(mode="json"),
        }

    async def run_operational_review(self, args: dict[str, Any]) -> ToolResult:
        run_id = _required_str(args, "run_id")
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_operational_review",
                args,
                self._run_operational_review_task,
                metadata={"run_id": run_id},
            )
            return ToolResult(
                tool_name="run_operational_review",
                status="queued",
                payload={"task": task.model_dump(mode="json")},
            )
        report = build_operational_review(
            run_id=run_id,
            policy=args.get("policy") if isinstance(args.get("policy"), str) else None,
            task=args.get("task") if isinstance(args.get("task"), str) else None,
            run_events=_event_dicts(args.get("run_events")),
            harness_condition_id=(
                args.get("harness_condition_id")
                if isinstance(args.get("harness_condition_id"), str)
                else None
            ),
        )
        self._context.telemetry.record_tool_call(
            "run_operational_review", args, "completed"
        )
        return ToolResult(
            tool_name="run_operational_review",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_operational_review_task(self, task: TaskRecord) -> dict[str, Any]:
        args = _metadata_args(task)
        self._tasks.update_progress(
            task.task_id, "running-operational-review", percent=50
        )
        report = build_operational_review(
            run_id=str(args.get("run_id") or task.run_id or task.task_id),
            policy=args.get("policy") if isinstance(args.get("policy"), str) else None,
            task=task.task_id,
            run_events=_event_dicts(args.get("run_events")),
            harness_condition_id=(
                args.get("harness_condition_id")
                if isinstance(args.get("harness_condition_id"), str)
                else None
            ),
        )
        return {"report": report.model_dump(mode="json")}

    async def run_readiness_audit(self, args: dict[str, Any]) -> ToolResult:
        repo_arg = args.get("repo")
        repo = str(repo_arg) if isinstance(repo_arg, str) else str(Path.cwd())
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_readiness_audit",
                args,
                self._run_readiness_audit_task,
                metadata={"repo": repo},
            )
            return ToolResult(
                tool_name="run_readiness_audit",
                status="queued",
                payload={"task": task.model_dump(mode="json")},
            )
        report = build_readiness_audit(
            repo=repo,
            policy=args.get("policy") if isinstance(args.get("policy"), str) else None,
            task=args.get("task") if isinstance(args.get("task"), str) else None,
        )
        self._context.telemetry.record_tool_call(
            "run_readiness_audit", args, "completed"
        )
        return ToolResult(
            tool_name="run_readiness_audit",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_readiness_audit_task(self, task: TaskRecord) -> dict[str, Any]:
        args = _metadata_args(task)
        self._tasks.update_progress(task.task_id, "running-readiness-audit", percent=50)
        repo = str(args.get("repo") or Path.cwd())
        report = build_readiness_audit(
            repo=repo,
            policy=args.get("policy") if isinstance(args.get("policy"), str) else None,
            task=task.task_id,
        )
        return {"report": report.model_dump(mode="json")}

    async def classify_patch_risk(self, args: dict[str, Any]) -> ToolResult:
        diff = _required_str(args, "diff")
        risk, feature_vector, context = classify_patch_risk(
            diff_text=diff,
            sarif_before=(
                args.get("sarif_before")
                if isinstance(args.get("sarif_before"), list)
                else None
            ),
            sarif_after=(
                args.get("sarif_after")
                if isinstance(args.get("sarif_after"), list)
                else None
            ),
            before_failed=(
                [str(item) for item in args.get("before_failed", [])]
                if isinstance(args.get("before_failed"), list)
                else None
            ),
            after_failed=(
                [str(item) for item in args.get("after_failed", [])]
                if isinstance(args.get("after_failed"), list)
                else None
            ),
            run_events=(
                [str(item) for item in args.get("run_events", [])]
                if isinstance(args.get("run_events"), list)
                else None
            ),
            run_id=args.get("run_id") if isinstance(args.get("run_id"), str) else None,
            snapshot_before=(
                args.get("snapshot_before")
                if isinstance(args.get("snapshot_before"), str)
                else None
            ),
            snapshot_after=(
                args.get("snapshot_after")
                if isinstance(args.get("snapshot_after"), str)
                else None
            ),
        )
        self._context.telemetry.record_tool_call(
            "classify_patch_risk", args, "completed"
        )
        return ToolResult(
            tool_name="classify_patch_risk",
            status="completed",
            payload={
                "risk": risk.model_dump(mode="json"),
                "feature_vector": feature_vector.model_dump(mode="json"),
                "diagnostics": context["scope"].missing_required_events,
            },
        )

    async def run_patch_review(self, args: dict[str, Any]) -> ToolResult:
        diff = _required_str(args, "diff")
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_patch_review", args, self._run_patch_review_task
            )
            return ToolResult(
                tool_name="run_patch_review",
                status="queued",
                payload={"task": task.model_dump(mode="json")},
            )
        report = run_patch_review(
            diff_text=diff,
            run_id=args.get("run_id") if isinstance(args.get("run_id"), str) else None,
            sampling_supported=sampling_supported(self._context.sampling)
            and bool(args.get("sampling_enabled", True)),
            sarif_before=(
                args.get("sarif_before")
                if isinstance(args.get("sarif_before"), list)
                else None
            ),
            sarif_after=(
                args.get("sarif_after")
                if isinstance(args.get("sarif_after"), list)
                else None
            ),
            before_failed=(
                [str(item) for item in args.get("before_failed", [])]
                if isinstance(args.get("before_failed"), list)
                else None
            ),
            after_failed=(
                [str(item) for item in args.get("after_failed", [])]
                if isinstance(args.get("after_failed"), list)
                else None
            ),
            run_events=(
                [str(item) for item in args.get("run_events", [])]
                if isinstance(args.get("run_events"), list)
                else None
            ),
        )
        self._context.telemetry.record_tool_call("run_patch_review", args, "completed")
        return ToolResult(
            tool_name="run_patch_review",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_patch_review_task(self, task: TaskRecord) -> dict[str, Any]:
        diff = _required_str(task.metadata["args"], "diff")
        report = run_patch_review(diff_text=diff)
        return {"report": report.model_dump(mode="json")}

    async def get_predicate_examples(self, args: dict[str, Any]) -> ToolResult:
        alert = args.get("alert")
        if isinstance(alert, dict):
            binding = bind_alert(alert)
            metadata = extract_predicate_metadata(binding)
        else:
            rule_id = _required_str(args, "rule_id")
            binding = bind_alert(
                {"alert_id": args.get("predicate_id", rule_id), "rule_id": rule_id}
            )
            metadata = extract_predicate_metadata(binding)
        examples, diagnostics = get_predicate_examples(
            metadata=metadata,
            target_repo_id=(
                args.get("repo") if isinstance(args.get("repo"), str) else None
            ),
            k=int(args.get("k", 5)),
        )
        return ToolResult(
            tool_name="get_predicate_examples",
            status="completed",
            payload={
                "examples": [example.model_dump(mode="json") for example in examples],
                "corpus": {"corpus_id": "local-fixture", "freshness": "static"},
            },
            diagnostics=[{"message": item} for item in diagnostics],
        )

    async def run_sast_repair(self, args: dict[str, Any]) -> ToolResult:
        alert = args.get("alert")
        if not isinstance(alert, dict):
            alert = {
                "alert_id": _required_str(args, "alert_id"),
                "rule_id": args.get("rule_id", "NULL_DEREF"),
                "file_path": args.get("file_path", "src/app.py"),
                "line": 1,
            }
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_sast_repair", args, self._run_sast_repair_task
            )
            return ToolResult(
                tool_name="run_sast_repair",
                status="queued",
                payload={"task": task.model_dump(mode="json")},
            )
        report = run_sast_repair(
            alert=alert,
            generate_patch=bool(args.get("generate_patch", True)),
            sandbox_root=self._context.config.workspace_path
            / ".llm-sca"
            / "sast-sandbox",
            suppression_history=(
                [str(item) for item in args.get("suppression_history", [])]
                if isinstance(args.get("suppression_history"), list)
                else None
            ),
            after_alerts=(
                args.get("after_alerts")
                if isinstance(args.get("after_alerts"), list)
                else None
            ),
            newly_failing_tests=(
                [str(item) for item in args.get("newly_failing_tests", [])]
                if isinstance(args.get("newly_failing_tests"), list)
                else None
            ),
        )
        return ToolResult(
            tool_name="run_sast_repair",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_sast_repair_task(self, task: TaskRecord) -> dict[str, Any]:
        args = task.metadata["args"]
        alert = args.get("alert")
        if not isinstance(alert, dict):
            alert = {
                "alert_id": _required_str(args, "alert_id"),
                "rule_id": "NULL_DEREF",
                "file_path": "src/app.py",
                "line": 1,
            }
        report = run_sast_repair(
            alert=alert,
            sandbox_root=self._context.config.workspace_path
            / ".llm-sca"
            / "sast-sandbox",
        )
        return {"report": report.model_dump(mode="json")}

    async def evolve_static_rules(self, args: dict[str, Any]) -> ToolResult:
        result = evolve_static_rules(
            ruleset=str(args.get("ruleset", "default")),
            sarif_deltas=(
                [str(item) for item in args.get("sarif_deltas", [])]
                if isinstance(args.get("sarif_deltas"), list)
                else []
            ),
        )
        return ToolResult(
            tool_name="evolve_static_rules",
            status="completed",
            payload=result,
        )

    async def run_issue_resolution(self, args: dict[str, Any]) -> ToolResult:
        issue_text = _required_str(args, "issue_text")
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_issue_resolution", args, self._run_issue_resolution_task
            )
            return ToolResult(
                tool_name="run_issue_resolution",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        report = run_issue_resolution(issue_text=issue_text)
        return ToolResult(
            tool_name="run_issue_resolution",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_issue_resolution_task(self, task: TaskRecord) -> dict[str, Any]:
        issue_text = _required_str(task.metadata["args"], "issue_text")
        report = run_issue_resolution(
            issue_text=issue_text,
        )
        return {"report": report.model_dump(mode="json"), "result_available": True}

    async def run_implementation_check(self, args: dict[str, Any]) -> ToolResult:
        spec = _required_str(args, "spec")
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_implementation_check", args, self._run_impl_check_task
            )
            return ToolResult(
                tool_name="run_implementation_check",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        report = run_implementation_check(spec=spec)
        return ToolResult(
            tool_name="run_implementation_check",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _run_impl_check_task(self, task: TaskRecord) -> dict[str, Any]:
        spec = _required_str(task.metadata["args"], "spec")
        report = run_implementation_check(spec=spec)
        return {"report": report.model_dump(mode="json"), "result_available": True}

    async def capture_trace(self, args: dict[str, Any]) -> ToolResult:
        script = _required_str(args, "script")
        if bool(args.get("task", False)):
            task = self._tasks.submit("capture_trace", args, self._capture_trace_task)
            return ToolResult(
                tool_name="capture_trace",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        result, compressed = await capture_trace(
            script=script,
            suspects=(
                [str(s) for s in args["suspects"]]
                if isinstance(args.get("suspects"), list)
                else None
            ),
            language=str(args.get("language", "python")),
            null_mode=bool(args.get("null_mode", True)),
        )
        payload: dict[str, Any] = {"result": result.model_dump(mode="json")}
        if compressed is not None:
            payload["compressed_trace"] = compressed.model_dump(mode="json")
        return ToolResult(
            tool_name="capture_trace",
            status="completed",
            payload=payload,
        )

    async def _capture_trace_task(self, task: TaskRecord) -> dict[str, Any]:
        script = _required_str(task.metadata["args"], "script")
        result, compressed = await capture_trace(
            script=script,
            null_mode=True,
        )
        payload: dict[str, Any] = {
            "result": result.model_dump(mode="json"),
            "result_available": True,
        }
        if compressed is not None:
            payload["compressed_trace"] = compressed.model_dump(mode="json")
        return payload

    async def record_trajectory(self, args: dict[str, Any]) -> ToolResult:
        import uuid as _uuid

        trajectory = TrajectoryRecord(
            trajectory_id=str(
                args.get("trajectory_id", f"traj:{_uuid.uuid4().hex[:8]}")
            ),
            repo_id=str(args.get("repo_id", "default")),
            workflow_type=str(args.get("workflow_type", "bug_resolve")),
            issue_class=str(args.get("issue_class", "unknown")),
            issue_text_hash=str(args.get("issue_text_hash", "unknown")),
            fl_decisions=[str(s) for s in args.get("fl_decisions", [])],
            graph_node_ids=[str(s) for s in args.get("graph_node_ids", [])],
            graph_snapshot_id=(
                args.get("graph_snapshot_id")
                if isinstance(args.get("graph_snapshot_id"), str)
                else None
            ),
            patch_diff_hash=(
                args.get("patch_diff_hash")
                if isinstance(args.get("patch_diff_hash"), str)
                else None
            ),
            patch_class=(
                args.get("patch_class")
                if isinstance(args.get("patch_class"), str)
                else None
            ),
            outcome=str(args.get("outcome", "uncertain")),
            source_run_id=str(args.get("source_run_id", "unknown")),
        )
        result = validate_and_write(trajectory, self._memory_store.policy)
        if result.written:
            self._memory_store.put_trajectory(trajectory)
        return ToolResult(
            tool_name="record_trajectory",
            status="completed" if result.written else "rejected",
            payload={
                "write_path_result": result.model_dump(mode="json"),
                "trajectory_id": trajectory.trajectory_id,
            },
        )

    async def retrieve_memory(self, args: dict[str, Any]) -> ToolResult:
        issue_text = _required_str(args, "issue_text")
        phase = str(args.get("phase", "investigate"))
        repo_id = str(args.get("repo", "default"))
        max_hints = int(args.get("max_hints", 5))
        try:
            from llm_sca_tooling.memory.policy import check_memory_enabled

            check_memory_enabled(self._memory_store.policy, repo_id)
        except MemoryDisabledError:
            return ToolResult(
                tool_name="retrieve_memory",
                status="completed",
                payload={
                    "status": "memory_disabled",
                    "active_hints": [],
                    "rejected_hints": [],
                    "weight": 0.0,
                },
            )
        if phase == "investigate":
            active_coarse, rejected_coarse = retrieve_coarse(
                issue_text, repo_id, self._memory_store, max_hints=max_hints
            )
            active: list[Any] = list(active_coarse)
            rejected: list[Any] = list(rejected_coarse)
            hint_type = "coarse"
        else:
            active_fine, rejected_fine = retrieve_fine(
                issue_text, repo_id, self._memory_store, max_hints=max_hints
            )
            active = list(active_fine)
            rejected = list(rejected_fine)
            hint_type = "fine"
        return ToolResult(
            tool_name="retrieve_memory",
            status="completed",
            payload={
                "hint_type": hint_type,
                "active_hints": [h.model_dump(mode="json") for h in active],
                "rejected_hints": [h.model_dump(mode="json") for h in rejected],
                "weight": 0.0,
            },
        )

    async def memory_compact(self, args: dict[str, Any]) -> ToolResult:
        repo_id = str(args.get("repo", "default"))
        dry_run = bool(args.get("dry_run", True))
        if bool(args.get("task", False)):
            task = self._tasks.submit("memory_compact", args, self._memory_compact_task)
            return ToolResult(
                tool_name="memory_compact",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        policy = EvictionPolicy()
        report = compact(repo_id, self._memory_store, policy, dry_run=dry_run)
        return ToolResult(
            tool_name="memory_compact",
            status="completed",
            payload={"report": report.model_dump(mode="json")},
        )

    async def _memory_compact_task(self, task: TaskRecord) -> dict[str, Any]:
        repo_id = str(task.metadata["args"].get("repo", "default"))
        dry_run = bool(task.metadata["args"].get("dry_run", True))
        policy = EvictionPolicy()
        report = compact(repo_id, self._memory_store, policy, dry_run=dry_run)
        return {"report": report.model_dump(mode="json"), "result_available": True}

    async def promote_operational_lesson(self, args: dict[str, Any]) -> ToolResult:
        import uuid as _uuid

        lesson = OperationalLesson(
            lesson_id=str(args.get("lesson_id", f"lesson:{_uuid.uuid4().hex[:8]}")),
            source_run_id=_required_str(args, "source_run_id"),
            trigger_condition=str(args.get("trigger_condition", "unknown")),
            lesson_type=str(args.get("lesson_type", "incident")),
            structured_content=(
                args.get("structured_content", {})
                if isinstance(args.get("structured_content"), dict)
                else {}
            ),
            target_type=str(args.get("target_type", "memory")),
            owner=str(args.get("owner", "unknown")),
            rollback_path=(
                args.get("rollback_path")
                if isinstance(args.get("rollback_path"), str)
                else None
            ),
            review_state=(
                "approved" if bool(args.get("review_approved", False)) else "unreviewed"
            ),
        )
        self._memory_store.put_lesson(lesson)
        try:
            updated, promoted_ref = promote_lesson(
                lesson,
                self._memory_store,
                review_approved=bool(args.get("review_approved", False)),
            )
            return ToolResult(
                tool_name="promote_operational_lesson",
                status="completed",
                payload={
                    "lesson": updated.model_dump(mode="json"),
                    "promoted_to_ref": promoted_ref,
                },
            )
        except UnreviewedLessonError as exc:
            return ToolResult(
                tool_name="promote_operational_lesson",
                status="rejected",
                payload={
                    "lesson": lesson.model_dump(mode="json"),
                    "error": str(exc),
                },
            )

    async def plugin_reload(self, args: dict[str, Any]) -> ToolResult:
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "plugin_reload", args, self._run_plugin_reload_task
            )
            return ToolResult(
                tool_name="plugin_reload",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        payload = await self._run_plugin_reload_args(args)
        notifications = [
            self._context.notifications.emit_list_changed().to_dict(),
            *[
                self._context.notifications.emit_updated(uri).to_dict()
                for uri in payload["notifications_emitted"]
                if isinstance(uri, str)
            ],
        ]
        return ToolResult(
            tool_name="plugin_reload",
            status=(
                "unavailable"
                if payload["diagnostics"] and not payload["plugins_reloaded"]
                else "completed"
            ),
            payload=payload,
            diagnostics=[
                {"message": str(item)} for item in payload.get("diagnostics", [])
            ],
            notifications=notifications,
        )

    async def trace_cross_language(self, args: dict[str, Any]) -> ToolResult:
        symbol = _required_str(args, "symbol")
        repo_id = args.get("repo")
        node_ids = await self._find_symbol_nodes(
            repo_id if isinstance(repo_id, str) else None, symbol
        )
        if not node_ids:
            raise ToolInvalidArguments("symbol could not be resolved")
        direction = TraversalDirection(str(args.get("direction", "both")))
        max_hops = int(args.get("max_hops", 10))
        plugins_arg = args.get("plugins")
        plugins = plugins_arg if isinstance(plugins_arg, list) else None
        result = await CrossLanguageTraverser(
            self._plugins, self._context.workspace
        ).traverse(
            node_ids[0],
            direction=direction,
            max_hops=max_hops,
            plugins=[str(item) for item in plugins] if plugins else None,
            min_confidence=str(args.get("min_confidence", "heuristic")),
        )
        payload = result.model_dump(mode="json")
        payload["start_symbol_path"] = symbol
        payload["languages_visited"] = []
        payload["repos_visited"] = [repo_id] if isinstance(repo_id, str) else []
        payload["run_event_ids"] = []
        payload["snapshot_ids"] = {}
        return ToolResult(
            tool_name="trace_cross_language",
            status="completed",
            payload=payload,
            diagnostics=[{"message": item} for item in result.diagnostics],
        )

    async def graph_build(self, args: dict[str, Any]) -> ToolResult:
        task = self._tasks.submit("graph_build", args, self._run_graph_build)
        self._context.telemetry.record_tool_call("graph_build", args, "accepted")
        return ToolResult(
            tool_name="graph_build",
            status="accepted",
            payload={"task": task.model_dump(mode="json")},
        )

    async def graph_update(self, args: dict[str, Any]) -> ToolResult:
        task = self._tasks.submit("graph_update", args, self._run_graph_update)
        self._context.telemetry.record_tool_call("graph_update", args, "accepted")
        return ToolResult(
            tool_name="graph_update",
            status="accepted",
            payload={"task": task.model_dump(mode="json")},
        )

    async def run_static_analysis(self, args: dict[str, Any]) -> ToolResult:
        if bool(args.get("task", False)):
            task = self._tasks.submit(
                "run_static_analysis", args, self._run_static_analysis_task
            )
            return ToolResult(
                tool_name="run_static_analysis",
                status="accepted",
                payload={"task": task.model_dump(mode="json")},
            )
        payload = await self._run_static_analysis_args(args)
        notifications = [
            self._context.notifications.emit_updated(
                str(payload["sarif_resource_uri"])
            ).to_dict()
        ]
        return ToolResult(
            tool_name="run_static_analysis",
            status="completed",
            payload=payload,
            notifications=notifications,
            diagnostics=payload.get("diagnostics", []),
        )

    async def task_status(self, args: dict[str, Any]) -> ToolResult:
        task = self._tasks.get(_required_str(args, "task_id"))
        return ToolResult(
            tool_name="task_status",
            status="completed",
            payload={"task": task.model_dump(mode="json")},
        )

    async def task_result(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name="task_result",
            status="completed",
            payload=self._tasks.result(_required_str(args, "task_id")),
        )

    async def task_cancel(self, args: dict[str, Any]) -> ToolResult:
        task = self._tasks.cancel(_required_str(args, "task_id"))
        return ToolResult(
            tool_name="task_cancel",
            status="completed",
            payload={"task": task.model_dump(mode="json")},
        )

    async def task_list(self, args: dict[str, Any]) -> ToolResult:
        tasks = [t.model_dump(mode="json") for t in self._tasks.list_tasks()]
        return ToolResult(
            tool_name="task_list", status="completed", payload={"tasks": tasks}
        )

    async def _run_graph_build(self, task: TaskRecord) -> dict[str, Any]:
        repo_path = await self._resolve_repo_path(task)
        self._tasks.update_progress(task.task_id, "graph_build", percent=30)
        result = await IndexingService(self._context.workspace).graph_build(repo_path)
        self._emit_index_notifications(result.repo_id)
        return _result_to_payload(result)

    async def _run_graph_update(self, task: TaskRecord) -> dict[str, Any]:
        repo_path = await self._resolve_repo_path(task)
        self._tasks.update_progress(task.task_id, "graph_update", percent=30)
        result = await IndexingService(self._context.workspace).graph_update(repo_path)
        self._emit_index_notifications(result.repo_id)
        return _result_to_payload(result)

    async def _run_static_analysis_task(self, task: TaskRecord) -> dict[str, Any]:
        self._tasks.update_progress(task.task_id, "analyser_started", percent=10)
        payload = await self._run_static_analysis_args(task.metadata.get("args") or {})
        self._tasks.update_progress(task.task_id, "notifications_emitted", percent=100)
        self._context.notifications.emit_updated(str(payload["sarif_resource_uri"]))
        return payload

    async def _run_plugin_reload_task(self, task: TaskRecord) -> dict[str, Any]:
        self._tasks.update_progress(task.task_id, "plugin_reload_started", percent=10)
        payload = await self._run_plugin_reload_args(task.metadata.get("args") or {})
        self._tasks.update_progress(task.task_id, "interfaces_updated", percent=100)
        self._context.notifications.emit_list_changed()
        return payload

    async def _run_plugin_reload_args(self, args: dict[str, Any]) -> dict[str, Any]:
        plugin_id = args.get("plugin_id")
        if plugin_id is not None and not isinstance(plugin_id, str):
            raise ToolInvalidArguments("plugin_id must be a string")
        repo_ids = args.get("repo_ids")
        if repo_ids is not None and not (
            isinstance(repo_ids, list)
            and all(isinstance(item, str) for item in repo_ids)
        ):
            raise ToolInvalidArguments("repo_ids must be a list of strings")
        return await reload_plugins(
            self._context.workspace,
            self._plugins,
            plugin_id=plugin_id,
            repo_ids=repo_ids,
        )

    async def _run_static_analysis_args(self, args: dict[str, Any]) -> dict[str, Any]:
        repo = _required_str(args, "repo")
        analyser = _required_str(args, "analyser")
        if analyser not in {"semgrep", "bandit", "codeql", "external"}:
            raise ToolInvalidArguments(
                "analyser must be semgrep, bandit, codeql, or external"
            )
        import_path = args.get("import_sarif_path")
        if import_path is not None and not isinstance(import_path, str):
            raise ToolInvalidArguments("import_sarif_path must be a string")
        ruleset = args.get("ruleset")
        if ruleset is not None and not isinstance(ruleset, (str, list)):
            raise ToolInvalidArguments("ruleset must be a string or list")
        payload = await run_static_analysis(
            self._context.workspace,
            repo=repo,
            analyser=analyser,
            import_sarif_path=import_path,
            ruleset=ruleset,
        )
        return dict(payload)

    async def _resolve_repo_path(self, task: TaskRecord) -> Path:
        args = task.metadata.get("args") or {}
        repo_path = args.get("repo_path")
        repo_id = args.get("repo_id")
        if isinstance(repo_path, str):
            path = Path(repo_path)
            if not path.exists() or not path.is_dir():
                raise ToolInvalidArguments("repo_path must be an existing directory")
            return path
        if isinstance(repo_id, str):
            repo = await self._context.workspace.registry.get_repo(repo_id)
            return repo.root_path
        raise ToolInvalidArguments("graph task requires repo_path or repo_id")

    async def _find_symbol_nodes(self, repo_id: str | None, symbol: str) -> list[str]:
        async with self._context.workspace._session_factory() as session:
            query = (
                "SELECT node_id FROM graph_nodes "
                "WHERE (node_id = :symbol OR qualified_name = :symbol "
                "OR label = :symbol)"
            )
            if repo_id:
                query += " AND repo_id = :repo_id"
            result = await session.execute(
                text(query), {"symbol": symbol, "repo_id": repo_id}
            )
            rows = result.all()
        return [str(row[0]) for row in rows]

    async def _fetch_calls(
        self, node_ids: list[str], *, direction: str, depth: int
    ) -> GraphSlice:
        async with self._context.workspace._session_factory() as session:
            if direction == "in":
                query = (
                    "SELECT source_id, target_id FROM graph_edges "
                    "WHERE edge_type = 'calls' AND target_id IN :node_ids"
                )
            else:
                query = (
                    "SELECT source_id, target_id FROM graph_edges "
                    "WHERE edge_type = 'calls' AND source_id IN :node_ids"
                )
            edge_rows = (
                await session.execute(
                    text(query).bindparams(bindparam("node_ids", expanding=True)),
                    {"node_ids": node_ids},
                )
            ).all()
        related = set(node_ids)
        for source_id, target_id in edge_rows:
            related.add(str(source_id))
            related.add(str(target_id))
        return await self._context.workspace.queries.fetch_ego_graph(
            list(related),
            depth=depth,
            edge_types=["calls"],
            limit=self._context.config.max_graph_slice_nodes,
        )

    def _emit_index_notifications(self, repo_id: str) -> None:
        for uri in [
            f"code-intelligence://graph/{repo_id}",
            f"code-intelligence://build-evidence/{repo_id}",
        ]:
            self._context.notifications.emit_updated(uri)


def _required_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise ToolInvalidArguments(f"{key} must be a non-empty string")
    return value


def _optional_int(args: dict[str, Any], key: str) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ToolInvalidArguments(f"{key} must be an integer")


def _event_dicts(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ToolInvalidArguments("run_events must be a list of objects")
    return [dict(item) for item in value]


def _metadata_args(task: TaskRecord) -> dict[str, Any]:
    args = task.metadata.get("args") or {}
    if not isinstance(args, dict):
        raise ToolInvalidArguments("task metadata args must be an object")
    return args


def _descriptor(
    name: str,
    description: str,
    *,
    read_only: bool,
    long_running: bool = False,
    task_support: str = "none",
    side_effect_class: str,
    required_mode: str,
    writes_to_store: bool = False,
    runs_subprocesses: bool = False,
    notifications: bool = False,
    input_schema: dict[str, Any] | None = None,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema or _object_schema({}),
        output_schema=_object_schema({"status": {"type": "string"}}),
        read_only=read_only,
        long_running=long_running,
        task_support=task_support,
        permissions=ToolPermissionDescriptor(
            required_mode=required_mode,
            path_scope="registered repos",
            side_effect_class=side_effect_class,
            writes_to_store=writes_to_store,
            runs_subprocesses=runs_subprocesses,
        ),
        emits_resource_notifications=notifications,
    )


def register_core_tools(
    registry: ToolRegistry, context: McpServerContext, tasks: TaskManager
) -> CoreToolHandlers:
    handlers = CoreToolHandlers(context, tasks)
    entries = [
        (
            _descriptor(
                "register_repo",
                "Register a repository without indexing it.",
                read_only=False,
                side_effect_class="writes_local_workspace",
                required_mode="read/search",
                writes_to_store=True,
                notifications=True,
                input_schema=_object_schema(
                    {"repo_path": {"type": "string"}, "name": {"type": "string"}},
                    ["repo_path"],
                ),
            ),
            handlers.register_repo,
        ),
        (
            _descriptor(
                "graph_build",
                "Start a full graph build as a task.",
                read_only=False,
                long_running=True,
                task_support="required",
                side_effect_class="writes_local_workspace",
                required_mode="execute",
                writes_to_store=True,
                runs_subprocesses=True,
                notifications=True,
                input_schema=_object_schema(
                    {"repo_path": {"type": "string"}, "repo_id": {"type": "string"}}
                ),
            ),
            handlers.graph_build,
        ),
        (
            _descriptor(
                "graph_update",
                "Start an incremental graph update as a task.",
                read_only=False,
                long_running=True,
                task_support="required",
                side_effect_class="writes_local_workspace",
                required_mode="execute",
                writes_to_store=True,
                runs_subprocesses=True,
                notifications=True,
            ),
            handlers.graph_update,
        ),
        (
            _descriptor(
                "plugin_reload",
                "Reload interface plugins for registered repositories.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_graph_nodes",
                required_mode="execute",
                writes_to_store=True,
                notifications=True,
                input_schema=_object_schema(
                    {
                        "plugin_id": {"type": "string"},
                        "repo_ids": {"type": "array"},
                        "task": {"type": "boolean"},
                    }
                ),
            ),
            handlers.plugin_reload,
        ),
        (
            _descriptor(
                "trace_cross_language",
                "Trace graph hops through registered interface plugins.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "symbol": {"type": "string"},
                        "direction": {"type": "string"},
                        "max_hops": {"type": "integer"},
                        "plugins": {"type": "array"},
                        "min_confidence": {"type": "string"},
                        "include_ambiguous": {"type": "boolean"},
                    },
                    ["symbol"],
                ),
            ),
            handlers.trace_cross_language,
        ),
        (
            _descriptor(
                "run_static_analysis",
                "Run or import static-analysis SARIF and bind alerts to graph nodes.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_sarif_store",
                required_mode="execute",
                writes_to_store=True,
                runs_subprocesses=True,
                notifications=True,
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "analyser": {"type": "string"},
                        "ruleset": {},
                        "files": {"type": "array"},
                        "snapshot": {"type": "string"},
                        "import_sarif_path": {"type": "string"},
                        "config": {"type": "object"},
                        "task": {"type": "boolean"},
                    },
                    ["repo", "analyser"],
                ),
            ),
            handlers.run_static_analysis,
        ),
        (
            _descriptor(
                "get_graph_slice",
                "Return a bounded typed graph slice.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {"repo": {"type": "string"}, "files": {"type": "array"}},
                    ["repo"],
                ),
            ),
            handlers.get_graph_slice,
        ),
        (
            _descriptor(
                "find_callers",
                "Return callers for a symbol using calls edges.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "symbol": {"type": "string"},
                        "depth": {"type": "integer"},
                        "include_cross_language": {"type": "boolean"},
                    },
                    ["symbol"],
                ),
            ),
            handlers.find_callers,
        ),
        (
            _descriptor(
                "find_callees",
                "Return callees for a symbol using calls edges.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "symbol": {"type": "string"},
                        "depth": {"type": "integer"},
                        "include_cross_language": {"type": "boolean"},
                    },
                    ["symbol"],
                ),
            ),
            handlers.find_callees,
        ),
        (
            _descriptor(
                "git_blame_chain",
                "Return git blame-chain evidence for a file.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                runs_subprocesses=True,
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    ["repo", "file"],
                ),
            ),
            handlers.git_blame_chain,
        ),
        (
            _descriptor(
                "classify_repo_question",
                "Classify a repository question without answering it.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "question": {"type": "string"},
                        "repos": {"type": "array"},
                        "use_llm_fallback": {"type": "boolean"},
                    },
                    ["question"],
                ),
            ),
            handlers.classify_repo_question,
        ),
        (
            _descriptor(
                "answer_repo_question",
                "Answer a repository question with cited graph evidence.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "question": {"type": "string"},
                        "repos": {"type": "array"},
                        "question_class_hint": {"type": "string"},
                        "synthesis": {"type": "boolean"},
                        "synthesis_mode": {"type": "string"},
                        "max_evidence": {"type": "integer"},
                        "max_hops": {"type": "integer"},
                        "snapshot": {"type": "string"},
                        "include_blame": {"type": "boolean"},
                        "budget": {"type": "object"},
                    },
                    ["question"],
                ),
            ),
            handlers.answer_repo_question,
        ),
        (
            _descriptor(
                "get_interface_contract",
                "Return a typed Phase 7 interface contract record.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "plugin_id": {"type": "string"},
                        "interface_name": {"type": "string"},
                        "repo": {"type": "string"},
                        "include_operations": {"type": "boolean"},
                        "include_node_refs": {"type": "boolean"},
                    },
                    ["plugin_id", "interface_name"],
                ),
            ),
            handlers.get_interface_contract,
        ),
        (
            _descriptor(
                "get_relevant_files",
                "Run fault localisation and return ranked relevant files.",
                read_only=True,
                task_support="optional",
                side_effect_class="writes_vector_cache",
                required_mode="read/search",
                writes_to_store=False,
                input_schema=_object_schema(
                    {
                        "issue_text": {"type": "string"},
                        "repos": {"type": "array"},
                        "failing_tests": {"type": "array"},
                        "coverage_path": {"type": "string"},
                        "max_files": {"type": "integer"},
                        "include_symbols": {"type": "boolean"},
                        "snapshot": {"type": "string"},
                        "use_embedding": {"type": "boolean"},
                        "budget": {"type": "object"},
                    },
                    ["issue_text"],
                ),
            ),
            handlers.get_relevant_files,
        ),
        (
            _descriptor(
                "compute_rds_features",
                "Compute and store an RDS v0.2 feature vector for an eval instance.",
                read_only=False,
                side_effect_class="writes_eval_store",
                required_mode="read/search",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "instance_id": {"type": "string"},
                        "eval_run_id": {"type": "string"},
                        "repo": {"type": "string"},
                        "snapshot": {"type": "string"},
                        "gold_patch_ref": {"type": "string"},
                    },
                    ["instance_id"],
                ),
            ),
            handlers.compute_rds_features,
        ),
        (
            _descriptor(
                "record_eval_result",
                "Store a typed evaluation run result and publish the eval resource.",
                read_only=False,
                side_effect_class="writes_eval_store",
                required_mode="read/search",
                writes_to_store=True,
                notifications=True,
                input_schema=_object_schema(
                    {"eval_run": {"type": "object"}},
                    ["eval_run"],
                ),
            ),
            handlers.record_eval_result,
        ),
        (
            _descriptor(
                "run_eval_suite",
                "Run a local T1, T3, or T4 evaluation suite in null mode.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_eval_store",
                required_mode="read/search",
                writes_to_store=True,
                notifications=True,
                input_schema=_object_schema(
                    {
                        "suite": {"type": "string"},
                        "target": {"type": "string"},
                        "instance_ids": {"type": "array"},
                        "model_backend": {"type": "string"},
                        "policy_id": {"type": "string"},
                        "harness_condition": {"type": "object"},
                        "null_mode": {"type": "boolean"},
                        "task": {"type": "boolean"},
                        "fixture_root": {"type": "string"},
                    }
                ),
            ),
            handlers.run_eval_suite,
        ),
        (
            _descriptor(
                "run_operational_review",
                "Run the Phase 18 operational review launcher.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_operational_report",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "run_id": {"type": "string"},
                        "policy": {"type": "string"},
                        "task": {"type": "boolean"},
                        "run_events": {"type": "array"},
                        "harness_condition_id": {"type": "string"},
                    },
                    ["run_id"],
                ),
            ),
            handlers.run_operational_review,
        ),
        (
            _descriptor(
                "run_readiness_audit",
                "Run the Phase 18 readiness audit launcher.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_readiness_report",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "policy": {"type": "string"},
                        "task": {"type": "boolean"},
                    }
                ),
            ),
            handlers.run_readiness_audit,
        ),
        (
            _descriptor(
                "classify_patch_risk",
                "Classify patch risk with deterministic Phase 11 gates.",
                read_only=False,
                side_effect_class="writes_patch_review_store",
                required_mode="read/search",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "diff": {"type": "string"},
                        "repo": {"type": "string"},
                        "snapshot_before": {"type": "string"},
                        "snapshot_after": {"type": "string"},
                        "sarif_before": {"type": "array"},
                        "sarif_after": {"type": "array"},
                        "run_id": {"type": "string"},
                        "run_events": {"type": "array"},
                        "before_failed": {"type": "array"},
                        "after_failed": {"type": "array"},
                    },
                    ["diff"],
                ),
            ),
            handlers.classify_patch_risk,
        ),
        (
            _descriptor(
                "run_patch_review",
                "Run four-axis patch review and merge-risk gates.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_patch_review_store",
                required_mode="read/search",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "diff": {"type": "string"},
                        "context": {"type": "object"},
                        "repos": {"type": "array"},
                        "policy": {"type": "string"},
                        "run_id": {"type": "string"},
                        "sampling_enabled": {"type": "boolean"},
                        "task": {"type": "boolean"},
                        "sarif_before": {"type": "array"},
                        "sarif_after": {"type": "array"},
                        "run_events": {"type": "array"},
                        "before_failed": {"type": "array"},
                        "after_failed": {"type": "array"},
                    },
                    ["diff"],
                ),
            ),
            handlers.run_patch_review,
        ),
        (
            _descriptor(
                "get_predicate_examples",
                "Retrieve PredicateFix-style clean-corpus examples for a SAST rule.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "predicate_id": {"type": "string"},
                        "rule_id": {"type": "string"},
                        "alert": {"type": "object"},
                        "repo": {"type": "string"},
                        "corpus": {"type": "string"},
                        "k": {"type": "integer"},
                    }
                ),
            ),
            handlers.get_predicate_examples,
        ),
        (
            _descriptor(
                "run_sast_repair",
                "Run the Phase 12 SAST repair loop in sandbox/null mode.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_sast_repair_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "alert_id": {"type": "string"},
                        "alert": {"type": "object"},
                        "repo": {"type": "string"},
                        "corpus": {"type": "string"},
                        "generate_patch": {"type": "boolean"},
                        "null_mode": {"type": "boolean"},
                        "task": {"type": "boolean"},
                        "rule_id": {"type": "string"},
                        "file_path": {"type": "string"},
                        "after_alerts": {"type": "array"},
                        "newly_failing_tests": {"type": "array"},
                        "suppression_history": {"type": "array"},
                    }
                ),
            ),
            handlers.run_sast_repair,
        ),
        (
            _descriptor(
                "evolve_static_rules",
                "Return the Phase 12 offline static-rule evolution stub.",
                read_only=False,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "sarif_deltas": {"type": "array"},
                        "ruleset": {"type": "string"},
                    }
                ),
            ),
            handlers.evolve_static_rules,
        ),
        (
            _descriptor(
                "run_issue_resolution",
                "Run the ten-stage bug-resolve workflow for an issue (null mode).",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_bug_resolve_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "issue_text": {"type": "string"},
                        "repos": {"type": "array"},
                        "budget": {"type": "object"},
                        "config": {"type": "object"},
                        "null_mode": {"type": "boolean"},
                        "task": {"type": "boolean"},
                    },
                    ["issue_text"],
                ),
            ),
            handlers.run_issue_resolution,
        ),
        (
            _descriptor(
                "run_implementation_check",
                "Run the seven-stage implementation-check DAG for a spec document.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_impl_check_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "spec": {"type": "string"},
                        "repos": {"type": "array"},
                        "policy": {"type": "string"},
                        "null_mode": {"type": "boolean"},
                        "task": {"type": "boolean"},
                    },
                    ["spec"],
                ),
            ),
            handlers.run_implementation_check,
        ),
        (
            _descriptor(
                "capture_trace",
                "Capture a scoped dynamic trace and return compressed evidence.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_trace_artefact",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "script": {"type": "string"},
                        "args": {"type": "array"},
                        "scope_filter": {"type": "object"},
                        "suspects": {"type": "array"},
                        "timeout_seconds": {"type": "integer"},
                        "language": {"type": "string"},
                        "pre_fix": {"type": "boolean"},
                        "post_fix": {"type": "boolean"},
                        "null_mode": {"type": "boolean"},
                        "task": {"type": "boolean"},
                    },
                    ["script"],
                ),
            ),
            handlers.capture_trace,
        ),
        (
            _descriptor(
                "record_trajectory",
                "Record a workflow trajectory to memory (write-path validated).",
                read_only=False,
                side_effect_class="writes_memory_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "trajectory_id": {"type": "string"},
                        "repo_id": {"type": "string"},
                        "workflow_type": {"type": "string"},
                        "issue_class": {"type": "string"},
                        "issue_text_hash": {"type": "string"},
                        "fl_decisions": {"type": "array"},
                        "graph_node_ids": {"type": "array"},
                        "graph_snapshot_id": {"type": "string"},
                        "patch_diff_hash": {"type": "string"},
                        "patch_class": {"type": "string"},
                        "outcome": {"type": "string"},
                        "source_run_id": {"type": "string"},
                    },
                    ["issue_text_hash", "outcome", "source_run_id"],
                ),
            ),
            handlers.record_trajectory,
        ),
        (
            _descriptor(
                "retrieve_memory",
                "Retrieve coarse/fine memory hints for an issue (soft context only).",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
                input_schema=_object_schema(
                    {
                        "issue_text": {"type": "string"},
                        "phase": {"type": "string"},
                        "repo": {"type": "string"},
                        "fl_result_ref": {"type": "string"},
                        "max_hints": {"type": "integer"},
                    },
                    ["issue_text"],
                ),
            ),
            handlers.retrieve_memory,
        ),
        (
            _descriptor(
                "memory_compact",
                "Apply eviction/retention policy to memory store.",
                read_only=False,
                long_running=True,
                task_support="optional",
                side_effect_class="writes_memory_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "repo": {"type": "string"},
                        "dry_run": {"type": "boolean"},
                        "task": {"type": "boolean"},
                    }
                ),
            ),
            handlers.memory_compact,
        ),
        (
            _descriptor(
                "promote_operational_lesson",
                "Promote a reviewed operational lesson to durable memory.",
                read_only=False,
                side_effect_class="writes_memory_store",
                required_mode="execute",
                writes_to_store=True,
                input_schema=_object_schema(
                    {
                        "lesson_id": {"type": "string"},
                        "source_run_id": {"type": "string"},
                        "source_event_id": {"type": "string"},
                        "target_type": {"type": "string"},
                        "structured_content": {"type": "object"},
                        "owner": {"type": "string"},
                        "expiry_ts": {"type": "string"},
                        "rollback_path": {"type": "string"},
                        "trigger_condition": {"type": "string"},
                        "lesson_type": {"type": "string"},
                        "review_approved": {"type": "boolean"},
                    },
                    ["source_run_id"],
                ),
            ),
            handlers.promote_operational_lesson,
        ),
        (
            _descriptor(
                "task_status",
                "Poll task status.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
            ),
            handlers.task_status,
        ),
        (
            _descriptor(
                "task_result",
                "Fetch task result.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
            ),
            handlers.task_result,
        ),
        (
            _descriptor(
                "task_cancel",
                "Cancel a queued or running task.",
                read_only=False,
                side_effect_class="updates_task_state",
                required_mode="read/search",
                writes_to_store=True,
            ),
            handlers.task_cancel,
        ),
        (
            _descriptor(
                "task_list",
                "List tasks when allowed by local policy.",
                read_only=True,
                side_effect_class="none",
                required_mode="read/search",
            ),
            handlers.task_list,
        ),
    ]
    for descriptor, handler in entries:
        registry.register(descriptor, handler)
    return handlers
