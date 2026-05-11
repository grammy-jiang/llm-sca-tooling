"""Public Phase 4 prompt stubs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_sca_tooling.mcp_server.errors import ResourceNotFound
from llm_sca_tooling.mcp_server.sampling import SamplingCapability

__all__ = ["PromptDescriptor", "PromptRegistry", "register_default_prompts"]


class PromptDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    argument_schema: dict[str, Any]
    resource_refs: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    instructions: str
    workflow_launcher: str
    limitation: str | None = None


class PromptRegistry:
    def __init__(self, sampling: SamplingCapability) -> None:
        self._sampling = sampling
        self._prompts: dict[str, PromptDescriptor] = {}

    def register(self, prompt: PromptDescriptor) -> None:
        if prompt.name in self._prompts:
            raise ValueError(f"duplicate prompt: {prompt.name}")
        self._prompts[prompt.name] = prompt

    def list_prompts(self) -> list[PromptDescriptor]:
        return list(self._prompts.values())

    def get(self, name: str) -> dict[str, Any]:
        try:
            prompt = self._prompts[name]
        except KeyError as exc:
            raise ResourceNotFound(f"Prompt {name!r} not found") from exc
        payload = prompt.model_dump(mode="json")
        payload["sampling"] = self._sampling.model_dump(mode="json")
        if prompt.limitation is not None:
            payload["limitation"] = prompt.limitation
        else:
            payload["limitation"] = (
                f"{prompt.workflow_launcher} is not implemented in Phase 4; "
                "this prompt only assembles evidence resources and suggested "
                "tool calls."
            )
        return payload


def _schema(*required: str) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "additionalProperties": False,
        "properties": {name: {"type": "string"} for name in required},
    }


def register_default_prompts(registry: PromptRegistry) -> None:
    registry.register(
        PromptDescriptor(
            name="implementation-check",
            description=(
                "Seven-stage implementation-check DAG: spec ingestion →"
                " clause extraction → intent graph → contract generation →"
                " grounding → static verdict → repo-QA probe → aggregation."
            ),
            argument_schema={
                "type": "object",
                "required": ["spec"],
                "additionalProperties": False,
                "properties": {
                    "spec": {"type": "string"},
                    "repos": {"type": "array"},
                    "policy": {"type": "string"},
                },
            },
            resource_refs=[
                "code-intelligence://repos",
                "code-intelligence://schema/graph.schema.json",
                "code-intelligence://build-evidence/{repo}",
                "code-intelligence://graph/slice/{repo}/{files}",
            ],
            suggested_tools=[
                "run_implementation_check",
                "task_status",
                "task_result",
                "get_graph_slice",
                "answer_repo_question",
            ],
            workflow_launcher="run_implementation_check",
            instructions=(
                "Call run_implementation_check(spec) as a task and poll to"
                " completion. Read the ImplementationCheckReport and"
                " ClauseVerdictMatrix. Report: per-clause verdicts"
                " (satisfied/violated/unknown), security and harness-policy"
                " clause summaries, overall_verdict, recommendation, and"
                " HarnessConditionSheet reference."
                " violated dominates all soft evidence unconditionally."
                " unknown is preserved when evidence is missing, grounding"
                " failed, or graph links are ambiguous."
                " Behaviour-tracing repo-QA alone cannot auto-pass"
                " high-stakes checks until accuracy reaches >=70%."
                " ECE <=0.10 is required for auto-pass gate."
                " Hard predicate failures dominate soft positive evidence."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="evaluate",
            description="Launch and report a structured evaluation suite.",
            argument_schema={
                "type": "object",
                "required": ["suite"],
                "additionalProperties": False,
                "properties": {
                    "suite": {"type": "string"},
                    "target": {"type": "string"},
                    "null_mode": {"type": "string"},
                },
            },
            resource_refs=[
                "code-intelligence://eval/{run_id}",
                "code-intelligence://eval/latest",
            ],
            suggested_tools=["run_eval_suite", "task_status", "task_result"],
            workflow_launcher="run_eval_suite",
            instructions=(
                "Read the Harness Condition Sheet metadata, launch run_eval_suite, "
                "poll until completion, then read code-intelligence://eval/{run_id}. "
                "Never report resolve-rate without FL-conditioned repair rate. "
                "Flag contamination canary suspect/contaminated before any quality "
                "claim, include suite freshness and manifest regression verdict, "
                "warn when process compliance is below 90%, and treat LLM-as-judge "
                "outputs as non-deterministic evidence. External-quality claims must "
                "use swe-bench-live as the headline suite."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="audit",
            description=(
                "Two-mode audit: patch (run_patch_review) or"
                " implementation_check (run_implementation_check)."
            ),
            argument_schema={
                "type": "object",
                "required": ["mode"],
                "additionalProperties": False,
                "properties": {
                    "mode": {"type": "string"},
                    "diff": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
            resource_refs=[],
            suggested_tools=[
                "run_patch_review",
                "run_implementation_check",
                "task_status",
                "task_result",
            ],
            workflow_launcher="run_patch_review",
            instructions=(
                "For mode=patch: call run_patch_review(diff) as a task, poll to"
                " completion, read the four axis findings, SARIF delta, DryRUN"
                " mismatches, scope audit, maintainability gate, operational"
                " verdict, and patch-risk class. Never claim merge-supporting"
                " when any deterministic block condition is active; never suppress"
                " DryRUN mismatches or SARIF alerts; include the Harness Condition"
                " Sheet reference."
                " For mode=implementation_check: call"
                " run_implementation_check(spec) as a task, poll to completion,"
                " read the ClauseVerdictMatrix. Report per-clause verdicts."
                " violated dominates all soft evidence unconditionally. unknown is"
                " preserved when evidence is missing or grounding failed. Never"
                " claim compliant when any clause is violated."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="risk-classify",
            description="Classify patch risk and report calibration status.",
            argument_schema={
                "type": "object",
                "required": ["diff"],
                "additionalProperties": False,
                "properties": {
                    "diff": {"type": "string"},
                    "repo": {"type": "string"},
                },
            },
            resource_refs=[],
            suggested_tools=["classify_patch_risk"],
            workflow_launcher="classify_patch_risk",
            instructions=(
                "Call classify_patch_risk(diff), report risk class, calibrated "
                "probability, ECE bucket, active overrides, calibration family, and "
                "feature-vector summary. Never present classifier output as a "
                "standalone merge decision; explicitly flag unknown calibration."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="sast-repair",
            description="Repair a SAST/SARIF alert with PredicateFix-style context.",
            argument_schema={
                "type": "object",
                "required": ["alert_id"],
                "additionalProperties": False,
                "properties": {
                    "alert_id": {"type": "string"},
                    "repo": {"type": "string"},
                },
            },
            resource_refs=[],
            suggested_tools=[
                "get_predicate_examples",
                "run_sast_repair",
                "task_status",
                "task_result",
            ],
            workflow_launcher="run_sast_repair",
            instructions=(
                "Call get_predicate_examples(alert_id), then run_sast_repair(alert_id) "
                "as a task and poll to completion. Report alert classification, "
                "predicate examples, SARIF delta, build/test result, patch-risk class, "
                "remaining-risk notes verbatim, Harness Condition Sheet reference, "
                "and run_id. Do not claim alert_fixed when original_alert_remains is "
                "true; never suppress new critical alerts; flag reviewer_required for "
                "suppression proposals."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="bug-resolve",
            description=(
                "Ten-stage bug-resolve workflow: investigate → repair → dryrun → "
                "gates → patch-risk → blast-radius → scope-audit → "
                "operational-review → trajectory → report."
            ),
            argument_schema={
                "type": "object",
                "required": ["issue_text"],
                "additionalProperties": False,
                "properties": {
                    "issue_text": {"type": "string"},
                    "repos": {"type": "array"},
                    "budget": {"type": "object"},
                },
            },
            resource_refs=[
                "code-intelligence://repos",
                "code-intelligence://graph/slice/{repo}/{files}",
                "code-intelligence://blame/{repo}/{file_path}",
                "code-intelligence://build-evidence/{repo}",
            ],
            suggested_tools=[
                "run_issue_resolution",
                "task_status",
                "task_result",
                "get_graph_slice",
                "find_callers",
                "run_sast_repair",
                "classify_patch_risk",
            ],
            workflow_launcher="run_issue_resolution",
            instructions=(
                "Call run_issue_resolution(issue_text) as a task and poll to"
                " completion. Read the BugResolveReport. Report: ranked"
                " suspects, selected patch, gate results"
                " (SARIF/build/test/interface), patch-risk class,"
                " blast-radius impact, scope-audit verdict, DryRUN"
                " prediction, and Harness Condition Sheet reference."
                " A merge-supporting recommendation requires"
                " process-compliant run AND all hard gates passing."
                " DryRUN/actual mismatches are reported in uncertainty"
                " and must be resolved or accepted as explicit residual"
                " risk. Process-noncompliant, trace-incomplete, or"
                " budget-exhausted runs produce recommendation: block."
                " Preserve unknown when evidence is stale, missing, or"
                " ambiguous."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="patch-review",
            description="Assemble evidence for a future patch review workflow.",
            argument_schema=_schema("diff"),
            resource_refs=[
                "code-intelligence://graph/slice/{repo}/{files}",
                "code-intelligence://build-evidence/{repo}",
            ],
            suggested_tools=["get_graph_slice", "find_callers"],
            workflow_launcher="run_patch_review",
            instructions=(
                "Sampling is optional; use resource reads as the fallback path."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="operational-review",
            description="Run a Phase 18 operational review and report compliance.",
            argument_schema=_schema("run_id"),
            resource_refs=[
                "code-intelligence://schema/run-record.schema.json",
                "code-intelligence://eval/{run_id}",
            ],
            suggested_tools=[
                "run_operational_review",
                "task_status",
                "task_result",
            ],
            workflow_launcher="run_operational_review",
            limitation="Phase 18 full launcher available in deterministic local mode.",
            instructions=(
                "Call run_operational_review(run_id) and poll task_status/task_result "
                "when launched as a task. Report process-compliance verdict as one "
                "of: process-compliant, process-noncompliant, trace-incomplete, "
                "budget-exhausted, needs-readiness-work. Include trace completeness, "
                "denied and approved actions, budget behaviour, compaction loss, "
                "verification adequacy, maintainability oracle results, lessons "
                "eligible for promotion, and HarnessConditionSheet reference. "
                "Do not infer a compliant verdict when run records or required "
                "events are missing."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="readiness-audit",
            description="Run a Phase 18 AI-readiness audit for a repository.",
            argument_schema=_schema("repo"),
            resource_refs=[
                "code-intelligence://repos",
                "code-intelligence://build-evidence/{repo}",
                "code-intelligence://governance/{repo}/manifest-state",
            ],
            suggested_tools=[
                "run_readiness_audit",
                "task_status",
                "task_result",
                "get_graph_slice",
            ],
            workflow_launcher="run_readiness_audit",
            limitation="Phase 18 full launcher available in deterministic local mode.",
            instructions=(
                "Call run_readiness_audit(repo) and report AI-readiness score, "
                "harness stage, drift findings, missing gates, weak docs/spec "
                "links, unprotected risky paths, absent scanners, and recommended "
                "readiness tasks. State autonomy thresholds as: S1 for assisted "
                "local workflows, S2 for autonomous repository workflows, and S3 "
                "for production release claims. Include the AI-readiness report "
                "reference and HarnessConditionSheet requirement for release use."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="investigate",
            description="Fault localisation + repo-QA investigation stage.",
            argument_schema={
                "type": "object",
                "required": ["issue_text"],
                "additionalProperties": False,
                "properties": {
                    "issue_text": {"type": "string"},
                    "repos": {"type": "array"},
                    "budget": {"type": "object"},
                },
            },
            resource_refs=[
                "code-intelligence://repos",
                "code-intelligence://graph/slice/{repo}/{files}",
            ],
            suggested_tools=[
                "get_graph_slice",
                "find_callers",
                "answer_repo_question",
            ],
            workflow_launcher="run_issue_resolution",
            instructions=(
                "Normalise the issue text. Call get_relevant_files(issue_text)."
                " For each top-3 suspect: call get_graph_slice and"
                " answer_repo_question for behavioural context. Assemble"
                " InvestigateResult with ranked suspects and agreement scores."
                " Flag stale snapshot when present. Repo-QA answers with"
                " confidence < 0.5 are supporting evidence only."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="repair",
            description="Candidate patch generation stage of bug-resolve.",
            argument_schema={
                "type": "object",
                "required": ["investigate_result"],
                "additionalProperties": False,
                "properties": {
                    "investigate_result": {"type": "object"},
                    "candidate_index": {"type": "integer"},
                    "issue_context": {"type": "string"},
                },
            },
            resource_refs=[
                "code-intelligence://graph/slice/{repo}/{files}",
                "code-intelligence://build-evidence/{repo}",
            ],
            suggested_tools=[
                "get_graph_slice",
                "run_sast_repair",
                "classify_patch_risk",
            ],
            workflow_launcher="run_issue_resolution",
            instructions=(
                "Load graph slice for top fault locations. Check cross-language"
                " interface contracts. If issue maps to SARIF alert: call"
                " run_sast_repair. Otherwise: generate unified diff from graph"
                " slice and summaries. Generate pre/postconditions, reproduction"
                " test (assertflip), and execution-free certificate. Return"
                " CandidatePatch with all refs. remaining-risk notes required"
                " for vulnerability-class patches without PoC+."
            ),
        )
    )
    registry.register(
        PromptDescriptor(
            name="blast-radius",
            description=(
                "Cross-language, cross-repo blast-radius analysis"
                " (Phase 15 full implementation)."
            ),
            argument_schema={
                "type": "object",
                "required": ["change_set"],
                "additionalProperties": False,
                "properties": {
                    "change_set": {"type": "array"},
                    "repos": {"type": "array"},
                },
            },
            resource_refs=["code-intelligence://graph/slice/{repo}/{files}"],
            suggested_tools=["get_graph_slice", "find_callers"],
            workflow_launcher="run_issue_resolution",
            instructions=(
                "Call BlastRadiusService.compute(change_set). Read the"
                " BlastRadiusReport. Report all eight impact groups"
                " (DIRECT_CALLERS, DOWNSTREAM_BEHAVIOURS, TESTS, INTERFACES,"
                " SERVICES, REPOSITORIES, SARIF_REACHABILITY, LINKED_DOCS_SPECS)"
                " with counts. Report generated-stub notes and ABI impact notes."
                " Separate confirmed from ambiguous links — never merge them."
                " State is_partial when cross-repo or ABI analysis unavailable."
                " Flag stale implementation-check verdicts in LINKED_DOCS_SPECS."
            ),
        )
    )
