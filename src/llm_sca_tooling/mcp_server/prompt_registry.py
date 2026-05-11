"""Prompt descriptors and registry."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from llm_sca_tooling.mcp_server.sampling import SamplingCapabilityRecord
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class PromptDescriptor(StrictBaseModel):
    name: str
    description: str
    arguments_schema: JsonObject


class PromptResult(StrictBaseModel):
    name: str
    instructions: str
    arguments_schema: JsonObject
    resource_references: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    sampling: SamplingCapabilityRecord
    workflow_available: bool = False


class PromptRegistry:
    def __init__(self, prompt_dir: Path, sampling: SamplingCapabilityRecord) -> None:
        self.prompt_dir = prompt_dir
        self.sampling = sampling
        self._descriptors = _prompt_descriptors()

    def list_descriptors(self) -> list[PromptDescriptor]:
        return [self._descriptors[name] for name in sorted(self._descriptors)]

    def get(self, name: str) -> PromptResult:
        if name not in self._descriptors:
            raise KeyError(f"prompt not found: {name}")
        descriptor = self._descriptors[name]
        path = self.prompt_dir / f"{name.replace('-', '_')}.md"
        instructions = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else descriptor.description
        )
        workflow_available = name in _available_workflow_prompts()
        return PromptResult(
            name=name,
            instructions=instructions,
            arguments_schema=descriptor.arguments_schema,
            resource_references=_prompt_resources(name),
            suggested_tools=_prompt_tools(name),
            constraints=[
                "Do not execute workflows during prompt retrieval.",
                "Preserve unknown when evidence is missing.",
                "Use typed resources and tool results before free-form claims.",
                (
                    "Workflow launcher is available."
                    if workflow_available
                    else "Workflow launcher is not available in this build."
                ),
            ],
            expected_outputs=[
                "structured evidence plan",
                "resource/tool checklist",
                (
                    "typed workflow report"
                    if workflow_available
                    else "explicit unavailable workflow launcher note"
                ),
            ],
            sampling=self.sampling,
            workflow_available=workflow_available,
        )


def _prompt_descriptors() -> dict[str, PromptDescriptor]:
    return {
        "implementation-check": PromptDescriptor(
            name="implementation-check",
            description="Assemble evidence plan for implementation checking.",
            arguments_schema=_schema(
                {"spec": "string", "repos": "array", "policy": "object"}, ["spec"]
            ),
        ),
        "bug-resolve": PromptDescriptor(
            name="bug-resolve",
            description="Assemble evidence plan for future bug resolution.",
            arguments_schema=_schema(
                {"issue_text": "string", "repos": "array", "budget": "object"},
                ["issue_text"],
            ),
        ),
        "patch-review": PromptDescriptor(
            name="patch-review",
            description="Assemble evidence plan for future patch review.",
            arguments_schema=_schema(
                {
                    "diff": "string",
                    "context": "object",
                    "repos": "array",
                    "policy": "object",
                },
                ["diff"],
            ),
        ),
        "operational-review": PromptDescriptor(
            name="operational-review",
            description="Assemble evidence plan for operational review.",
            arguments_schema=_schema(
                {"run_id": "string", "policy": "object"}, ["run_id"]
            ),
        ),
        "readiness-audit": PromptDescriptor(
            name="readiness-audit",
            description="Assemble evidence plan for readiness audit.",
            arguments_schema=_schema({"repo": "string", "policy": "object"}, ["repo"]),
        ),
        "evaluate": PromptDescriptor(
            name="evaluate",
            description=(
                "Phase 10 evaluation harness: run T1 smoke suite and report HCS, "
                "FL metrics, RDS summary, freshness, and contamination canary verdict."
            ),
            arguments_schema=_schema(
                {"suite": "string", "null_mode": "boolean", "instance_ids": "array"},
                [],
            ),
        ),
        "investigate": PromptDescriptor(
            name="investigate",
            description=(
                "Phase 9 fault-localisation investigation: assemble evidence plan "
                "from issue text and ranked file candidates."
            ),
            arguments_schema=_schema(
                {"issue_text": "string", "repos": "array", "budget": "object"},
                ["issue_text"],
            ),
        ),
        "repair": PromptDescriptor(
            name="repair",
            description=(
                "Phase 13 repair workflow: generate and validate a patch from "
                "fault-localisation candidates."
            ),
            arguments_schema=_schema(
                {"issue_text": "string", "repos": "array", "diff": "string"},
                ["issue_text"],
            ),
        ),
        "audit": PromptDescriptor(
            name="audit",
            description=(
                "Phase 18 readiness audit: assess repository agent-readiness score "
                "across five axes."
            ),
            arguments_schema=_schema({"repo": "string", "policy": "object"}, ["repo"]),
        ),
        "blast-radius": PromptDescriptor(
            name="blast-radius",
            description=(
                "Blast-radius analysis: estimate impact scope of a proposed patch "
                "using cross-language graph traversal."
            ),
            arguments_schema=_schema(
                {"diff": "string", "repos": "array", "budget": "object"}, ["diff"]
            ),
        ),
        "sast-repair": PromptDescriptor(
            name="sast-repair",
            description=(
                "Phase 12 SAST repair loop: bind a SARIF alert, retrieve predicate "
                "examples, and generate a candidate fix."
            ),
            arguments_schema=_schema(
                {"alert": "object", "repos": "array", "corpus_root": "string"},
                ["alert", "corpus_root"],
            ),
        ),
        "risk-classify": PromptDescriptor(
            name="risk-classify",
            description=(
                "Patch risk classifier: derive a deterministic risk class and "
                "calibrated probability for a diff."
            ),
            arguments_schema=_schema(
                {"diff": "string", "repos": "array", "policy": "object"}, ["diff"]
            ),
        ),
    }


def _available_workflow_prompts() -> set[str]:
    """Prompts with registered workflow launcher tools in the current server."""
    return {
        "implementation-check",
        "bug-resolve",
        "patch-review",
        "operational-review",
        "readiness-audit",
        "evaluate",
        "sast-repair",
        "risk-classify",
    }


def _schema(properties: dict[str, str], required: list[str]) -> JsonObject:
    return {
        "type": "object",
        "properties": {name: {"type": kind} for name, kind in properties.items()},
        "required": required,
        "additionalProperties": False,
    }


def _prompt_resources(name: str) -> list[str]:
    common = [
        "code-intelligence://repos",
        "code-intelligence://schema/graph.schema.json",
    ]
    mapping = {
        "implementation-check": common
        + [
            "code-intelligence://graph/{repo}",
            "code-intelligence://build-evidence/{repo}",
        ],
        "bug-resolve": common
        + [
            "code-intelligence://graph/slice/{repo}/{files}",
            "code-intelligence://summary/{repo}/{symbol_path}",
            "code-intelligence://blame/{repo}/{file_path}",
        ],
        "patch-review": common
        + [
            "code-intelligence://graph/slice/{repo}/{files}",
            "code-intelligence://build-evidence/{repo}",
        ],
        "operational-review": ["code-intelligence://schema/run-record.schema.json"],
        "readiness-audit": common + ["code-intelligence://build-evidence/{repo}"],
        "evaluate": [
            "code-intelligence://eval/{run_id}",
            "code-intelligence://runs/{run_id}/harness-condition",
        ],
        "investigate": common
        + [
            "code-intelligence://graph/slice/{repo}/{files}",
            "code-intelligence://blame/{repo}/{file_path}",
        ],
        "repair": common
        + [
            "code-intelligence://graph/slice/{repo}/{files}",
            "code-intelligence://blame/{repo}/{file_path}",
            "code-intelligence://sarif/{repo}",
        ],
        "audit": common + ["code-intelligence://readiness/{repo}"],
        "blast-radius": common
        + [
            "code-intelligence://graph/{repo}",
            "code-intelligence://graph/slice/{repo}/{files}",
        ],
        "sast-repair": common
        + [
            "code-intelligence://sarif/{repo}",
            "code-intelligence://sarif/{repo}/{run_id}",
        ],
        "risk-classify": common
        + [
            "code-intelligence://graph/slice/{repo}/{files}",
            "code-intelligence://sarif/{repo}",
        ],
    }
    return mapping[name]


def _prompt_tools(name: str) -> list[str]:
    mapping = {
        "implementation-check": [
            "get_graph_slice",
            "graph_update",
            "run_implementation_check",
        ],
        "bug-resolve": [
            "get_graph_slice",
            "find_callers",
            "find_callees",
            "git_blame_chain",
            "run_issue_resolution",
        ],
        "patch-review": ["get_graph_slice", "run_patch_review"],
        "operational-review": ["run_operational_review"],
        "readiness-audit": ["register_repo", "run_readiness_audit"],
        "evaluate": ["run_eval_suite", "record_eval_result", "compute_rds_features"],
        "investigate": [
            "get_relevant_files",
            "get_graph_slice",
            "git_blame_chain",
        ],
        "repair": [
            "get_relevant_files",
            "get_graph_slice",
            "run_issue_resolution",
        ],
        "audit": ["register_repo", "run_readiness_audit", "compute_readiness_score"],
        "blast-radius": [
            "get_graph_slice",
            "find_callers",
            "find_callees",
            "trace_cross_language",
        ],
        "sast-repair": ["run_sast_repair", "get_graph_slice"],
        "risk-classify": ["classify_patch_risk", "get_graph_slice"],
    }
    return mapping[name]
