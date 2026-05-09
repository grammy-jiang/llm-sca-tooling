"""Phase 8 repository QA MCP tools."""

from __future__ import annotations

from llm_sca_tooling.mcp_server.context import McpRequestContext
from llm_sca_tooling.mcp_server.errors import ToolInvalidArguments
from llm_sca_tooling.mcp_server.serialization import to_jsonable
from llm_sca_tooling.mcp_server.tool_permissions import ToolPermissionDescriptor
from llm_sca_tooling.mcp_server.tool_registry import (
    ToolDescriptor,
    ToolHandler,
    ToolResult,
)
from llm_sca_tooling.qa.interface_lookup import InterfaceContractLookup
from llm_sca_tooling.qa.service import RepoQAService
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
    name: str, description: str, input_schema: JsonObject
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema={"type": "object"},
        read_only=True,
        permission=ToolPermissionDescriptor(
            required_mode=PermissionMode.SEARCH,
            path_scope="registered_repo",
            network_requirement="none",
            side_effect_class=SideEffectClass.NONE,
            writes_to_store=False,
            writes_to_repo=False,
            runs_subprocesses=False,
        ),
    )


class ClassifyRepoQuestionTool(ToolHandler):
    descriptor = _descriptor(
        "classify_repo_question",
        "Classify a repository question for deterministic QA routing.",
        _schema(
            {
                "question": {"type": "string"},
                "repos": {"type": "array", "items": {"type": "string"}},
                "use_llm_fallback": {"type": "boolean"},
            },
            ["question"],
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        question_text = args.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            raise ToolInvalidArguments("question is required")
        repos = (
            [str(item) for item in args.get("repos", [])] if args.get("repos") else None
        )
        question, result = RepoQAService(context.workspace).classify(
            question_text,
            repos=repos,
            use_llm_fallback=bool(args.get("use_llm_fallback", False)),
        )
        payload = result.model_dump(mode="json")
        payload["normalized_text"] = question.normalized_text
        payload["code_tokens"] = question.code_tokens
        payload["run_event_ids"] = []
        return ToolResult(
            tool_name=self.descriptor.name, status="completed", payload=payload
        )


class AnswerRepoQuestionTool(ToolHandler):
    descriptor = _descriptor(
        "answer_repo_question",
        "Answer repository questions with graph-backed evidence citations.",
        _schema(
            {
                "question": {"type": "string"},
                "repos": {"type": "array", "items": {"type": "string"}},
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
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        question_text = args.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            raise ToolInvalidArguments("question is required")
        repos = (
            [str(item) for item in args.get("repos", [])] if args.get("repos") else None
        )
        answer = RepoQAService(context.workspace).answer(
            question_text,
            repos=repos,
            question_class_hint=(
                str(args["question_class_hint"])
                if args.get("question_class_hint")
                else None
            ),
            synthesis=bool(args.get("synthesis", True)),
            synthesis_mode=(
                str(args["synthesis_mode"]) if args.get("synthesis_mode") else None
            ),
            max_evidence=int(args.get("max_evidence") or 20),
            max_hops=int(args.get("max_hops") or 8),
            snapshot=str(args["snapshot"]) if args.get("snapshot") else None,
            include_blame=bool(args.get("include_blame", False)),
            budget=args.get("budget") if isinstance(args.get("budget"), dict) else None,
        )
        return ToolResult(
            tool_name=self.descriptor.name,
            status="completed",
            payload=to_jsonable(answer),
        )


class GetInterfaceContractTool(ToolHandler):
    descriptor = _descriptor(
        "get_interface_contract",
        "Return a typed Phase 7 interface contract record.",
        _schema(
            {
                "plugin_id": {"type": "string"},
                "interface_name": {"type": "string"},
                "repo": {"type": "string"},
                "include_operations": {"type": "boolean"},
                "include_node_refs": {"type": "boolean"},
            },
            ["plugin_id", "interface_name"],
        ),
    )

    def call(self, context: McpRequestContext, args: JsonObject) -> ToolResult:
        plugin_id = args.get("plugin_id")
        interface_name = args.get("interface_name")
        if not isinstance(plugin_id, str) or not isinstance(interface_name, str):
            raise ToolInvalidArguments("plugin_id and interface_name are required")
        result = InterfaceContractLookup(context.workspace).lookup_record(
            plugin_id,
            interface_name,
            include_operations=bool(args.get("include_operations", True)),
            include_node_refs=bool(args.get("include_node_refs", True)),
        )
        if result is None:
            raise ToolInvalidArguments(
                f"interface not found: {plugin_id}/{interface_name}"
            )
        payload = result.model_dump(mode="json")
        payload["generated_artifact_refs"] = [
            artifact.model_dump(mode="json")
            for artifact in result.interface_record.generated_artifacts
        ]
        payload["snapshot_ids"] = result.interface_record.snapshot_ids
        payload["run_event_ids"] = []
        return ToolResult(
            tool_name=self.descriptor.name, status="completed", payload=payload
        )
