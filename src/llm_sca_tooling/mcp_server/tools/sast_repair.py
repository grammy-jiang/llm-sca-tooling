"""Phase 12 SAST-repair MCP tool handlers."""

from __future__ import annotations

import asyncio
import hashlib
import json
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
from llm_sca_tooling.sast_repair.corpus_adapter import (
    CleanCorpusAdapter,
    LocalFixtureCorpusAdapter,
)
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.report import run_sast_repair
from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules
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


def _store_artifact(context: McpRequestContext, payload: str, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    artifact_dir = context.workspace.artifact_root / "sast_repair"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{kind}_{digest[:24]}.json"
    path.write_text(payload + "\n", encoding="utf-8")
    ref = ArtifactRef(
        artifact_id=f"art:sast-repair-{kind}:{digest[:24]}",
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


def _adapter_for(args: JsonObject) -> CleanCorpusAdapter:
    corpus_root = args.get("corpus_root")
    corpus_id = str(args.get("corpus") or "local-fixture")
    if not isinstance(corpus_root, str) or not corpus_root.strip():
        raise ToolInvalidArguments("corpus_root is required")
    return LocalFixtureCorpusAdapter(
        corpus_root=Path(corpus_root),
        corpus_id=corpus_id,
        target_repo_id=(
            str(args["target_repo_id"]) if args.get("target_repo_id") else None
        ),
    )


_GET_PREDICATE_EXAMPLES_INPUT = _schema(
    {
        "predicate_id": {"type": "string"},
        "rule_id": {"type": "string"},
        "corpus": {"type": "string"},
        "corpus_root": {"type": "string"},
        "target_repo_id": {"type": "string"},
        "k": {"type": "integer"},
        "sarif_rule": {"type": "object"},
    },
    ["rule_id", "corpus_root"],
)


class GetPredicateExamplesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="get_predicate_examples",
        description=(
            "Retrieve PredicateFix-style examples for a SARIF alert: predicate "
            "negation first, rule-family fallback otherwise, embedding only as "
            "last resort. Returns typed PredicateExampleRecord list."
        ),
        input_schema=_GET_PREDICATE_EXAMPLES_INPUT,
        output_schema={"type": "object"},
        read_only=True,
        long_running=False,
        task_support="none",
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
        rule_id = args.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ToolInvalidArguments("rule_id is required")
        adapter = _adapter_for(args)
        sarif_rule = (
            args.get("sarif_rule") if isinstance(args.get("sarif_rule"), dict) else None
        )
        metadata = extract_predicate_metadata(rule_id=rule_id, sarif_rule=sarif_rule)
        k = int(args.get("k") or 5)
        examples, diagnostics = get_predicate_examples(
            metadata=metadata, adapter=adapter, k=k
        )
        payload = {
            "rule_id": rule_id,
            "predicate_metadata": metadata.model_dump(mode="json"),
            "examples": [rec.model_dump(mode="json") for rec in examples],
            "diagnostics": diagnostics,
            "corpus_id": adapter.corpus_id,
            "corpus_version": adapter.corpus_version,
        }
        artifact = _store_artifact(
            context, json.dumps(payload, indent=2, sort_keys=True), "examples"
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=payload,
            artifact_refs=[artifact],
            diagnostics=diagnostics,
        )


_RUN_SAST_REPAIR_INPUT = _schema(
    {
        "alert": {"type": "object"},
        "repo": {"type": "string"},
        "repo_root": {"type": "string"},
        "corpus_root": {"type": "string"},
        "corpus": {"type": "string"},
        "target_repo_id": {"type": "string"},
        "before_alerts": {"type": "array", "items": {"type": "object"}},
        "after_alerts": {"type": "array", "items": {"type": "object"}},
        "sarif_run_before_id": {"type": "string"},
        "sarif_run_after_id": {"type": "string"},
        "file_node_lookup": {"type": "object"},
        "graph_snapshot_id": {"type": "string"},
        "sarif_snapshot_id": {"type": "string"},
        "classification_signals": {"type": "object"},
        "null_mode": {"type": "boolean"},
        "generate_patch": {"type": "boolean"},
        "analyser_id": {"type": "string"},
        "analyser_version": {"type": "string"},
        "permission_mode": {"type": "string"},
        "run_id": {"type": "string"},
        "k": {"type": "integer"},
        "poc_plus_available": {"type": "boolean"},
        "graph_dataflow_complete": {"type": "boolean"},
    },
    ["alert", "corpus_root"],
)


class RunSastRepairTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="run_sast_repair",
        description=(
            "Execute the Phase 12 SAST repair loop for a single alert: "
            "bind, classify, retrieve predicate examples, build context, "
            "(optionally) generate a patch via the null adapter, sandbox, "
            "rerun analyser, verify SARIF delta, run tests, and return a "
            "SASTRepairReport with HarnessConditionSheet."
        ),
        input_schema=_RUN_SAST_REPAIR_INPUT,
        output_schema={"type": "object"},
        read_only=False,
        long_running=True,
        task_support="optional",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.EXECUTE,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.READ_ONLY,
            writes_to_store=True,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        alert = args.get("alert")
        if not isinstance(alert, dict):
            raise ToolInvalidArguments("alert is required and must be an object")
        adapter = _adapter_for(args)
        repo_root_arg = args.get("repo_root")
        repo_root = (
            Path(str(repo_root_arg)).expanduser().resolve()
            if isinstance(repo_root_arg, str) and repo_root_arg.strip()
            else None
        )
        report, sheet = asyncio.run(
            run_sast_repair(
                alert=dict(alert),
                repo_root=repo_root,
                corpus_adapter=adapter,
                before_alerts=list(args.get("before_alerts") or []),
                after_alerts=list(args.get("after_alerts") or []),
                sarif_run_before_id=(
                    str(args["sarif_run_before_id"])
                    if args.get("sarif_run_before_id")
                    else None
                ),
                sarif_run_after_id=(
                    str(args["sarif_run_after_id"])
                    if args.get("sarif_run_after_id")
                    else None
                ),
                file_node_lookup=(
                    dict(args["file_node_lookup"])
                    if isinstance(args.get("file_node_lookup"), dict)
                    else None
                ),
                graph_snapshot_id=(
                    str(args["graph_snapshot_id"])
                    if args.get("graph_snapshot_id")
                    else None
                ),
                sarif_snapshot_id=(
                    str(args["sarif_snapshot_id"])
                    if args.get("sarif_snapshot_id")
                    else None
                ),
                classification_signals=(
                    dict(args["classification_signals"])
                    if isinstance(args.get("classification_signals"), dict)
                    else None
                ),
                null_mode=bool(args.get("null_mode", True)),
                generate_patch=bool(args.get("generate_patch", False)),
                analyser_id=str(args.get("analyser_id") or "semgrep"),
                analyser_version=(
                    str(args["analyser_version"])
                    if args.get("analyser_version")
                    else None
                ),
                permission_mode=str(args.get("permission_mode") or "search"),
                run_id=str(args["run_id"]) if args.get("run_id") else None,
                k=int(args.get("k") or 5),
                poc_plus_available=bool(args.get("poc_plus_available", False)),
                graph_dataflow_complete=bool(
                    args.get("graph_dataflow_complete", False)
                ),
            )
        )
        payload: dict[str, Any] = {
            "report": report.model_dump(mode="json"),
            "harness_condition": sheet.model_dump(mode="json"),
        }
        artifact = _store_artifact(
            context, json.dumps(payload, indent=2, sort_keys=True), "report"
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=payload,
            artifact_refs=[artifact],
            diagnostics=list(report.diagnostics),
        )


_EVOLVE_STATIC_RULES_INPUT = _schema(
    {
        "sarif_deltas": {"type": "array", "items": {"type": "object"}},
        "ruleset": {"type": "string"},
    }
)


class EvolveStaticRulesTool(ToolHandler):
    descriptor = ToolDescriptor(
        name="evolve_static_rules",
        description=(
            "Phase 12 stub for the offline rule-evolution workflow. Returns "
            "not_implemented_in_phase_12 with a documented promotion gate "
            "(>=10pp FP reduction at k=5, zero TP loss, reviewable candidate, "
            "offline workspace)."
        ),
        input_schema=_EVOLVE_STATIC_RULES_INPUT,
        output_schema={"type": "object"},
        read_only=True,
        long_running=False,
        task_support="none",
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.READ,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.NONE,
            writes_to_store=False,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        result = evolve_static_rules(
            sarif_deltas=list(args.get("sarif_deltas") or []),
            ruleset=str(args["ruleset"]) if args.get("ruleset") else None,
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="unavailable",
            payload=result,
            diagnostics=[{"code": "not_implemented_in_phase_12"}],
        )


__all__ = [
    "GetPredicateExamplesTool",
    "RunSastRepairTool",
    "EvolveStaticRulesTool",
]
