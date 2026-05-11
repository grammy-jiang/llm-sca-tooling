from __future__ import annotations

import asyncio
from abc import ABC

import orjson
import pytest
from pydantic import ValidationError

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.sampling import SamplingCapability
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.analyser_rerun import rerun_analyser
from llm_sca_tooling.sast_repair.build_test_runner import run_build_and_tests
from llm_sca_tooling.sast_repair.corpus_adapter import LocalFixtureCorpusAdapter
from llm_sca_tooling.sast_repair.models import AlertBinding
from llm_sca_tooling.sast_repair.patch_generator import (
    NullPatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.remaining_risk import make_remaining_risk_note
from llm_sca_tooling.sast_repair.repair_context import build_repair_context
from llm_sca_tooling.sast_repair.report import run_sast_repair
from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules
from llm_sca_tooling.sast_repair.sandbox import apply_patch_in_sandbox
from llm_sca_tooling.sast_repair.sarif_delta_verifier import verify_sarif_delta
from llm_sca_tooling.sast_repair.suppression import propose_suppression

NULL_ALERT = {
    "alert_id": "a1",
    "rule_id": "NULL_DEREF",
    "file_path": "src/app.py",
    "line": 10,
}
INJECTION_ALERT = {
    "alert_id": "a2",
    "rule_id": "CWE-89",
    "file_path": "src/db.py",
    "line": 4,
    "cwe_ids": ["CWE-89"],
}


def test_models_binding_and_classification() -> None:
    binding = bind_alert(NULL_ALERT, graph_snapshot_id="snap")
    assert binding.confidence == "parser"
    assert binding.primary_symbol_node_ids
    assert AlertBinding.model_validate_json(binding.model_dump_json()) == binding
    with pytest.raises(ValidationError):
        AlertBinding.model_validate({"alert_id": "x"})
    no_location = bind_alert({"alert_id": "missing", "rule_id": "R"})
    assert "no_location" in no_location.diagnostics
    stale = bind_alert(NULL_ALERT)
    assert "stale_or_missing_snapshot" in stale.diagnostics
    true_positive = classify_alert(binding)
    false_positive = classify_alert(
        bind_alert({**NULL_ALERT, "file_path": "tests/test_app.py"}),
        suppression_history=["reviewed"],
    )
    unknown = classify_alert(bind_alert({"alert_id": "u", "rule_id": "UNKNOWN"}))
    assert true_positive.classification == "likely_true_positive"
    assert false_positive.classification == "likely_false_positive"
    assert unknown.classification == "unknown"


def test_predicate_metadata_examples_and_context(tmp_path) -> None:
    binding = bind_alert(INJECTION_ALERT, graph_snapshot_id="snap")
    classification = classify_alert(binding)
    metadata = extract_predicate_metadata(binding)
    examples, diagnostics = get_predicate_examples(
        metadata=metadata, target_repo_id="target"
    )
    assert metadata.negated_predicate_text is not None
    assert examples[0].retrieval_method == "predicate_negation"
    assert diagnostics == []
    fallback_meta = extract_predicate_metadata(
        bind_alert({"alert_id": "x", "rule_id": "UNKNOWN"})
    )
    fallback, fallback_diagnostics = get_predicate_examples(metadata=fallback_meta)
    assert fallback == []
    assert "predicate_negation_unavailable" in fallback_diagnostics
    adapter = LocalFixtureCorpusAdapter()
    assert adapter.supports_predicate_query() is True
    assert adapter.query_by_embedding([], 1) == []
    corpus_file = tmp_path / "examples.json"
    corpus_file.write_bytes(orjson.dumps([examples[0].model_dump(mode="json")]))
    loaded_adapter = LocalFixtureCorpusAdapter(tmp_path)
    assert loaded_adapter.query_by_predicate("CWE-89", "predicate") == []
    context = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=examples,
    )
    assert context.budget_remaining > 0
    assert "Correct pattern" in context.alert_explanation


def test_patch_generator_suppression_sandbox_and_rerun(tmp_path) -> None:
    binding = bind_alert(NULL_ALERT, graph_snapshot_id="snap")
    classification = classify_alert(binding)
    metadata = extract_predicate_metadata(binding)
    examples, _ = get_predicate_examples(metadata=metadata)
    context = build_repair_context(
        binding=binding,
        classification=classification,
        metadata=metadata,
        examples=examples,
    )
    assert issubclass(PatchGeneratorInterface, ABC)
    patch = NullPatchGenerator().generate(context)
    sandbox = apply_patch_in_sandbox(patch=patch, workspace_root=tmp_path)
    rerun = rerun_analyser(alert_id=binding.alert_id, sandbox=sandbox)
    assert patch.generation_method == "null_repair"
    assert sandbox.patch_applied is True
    assert rerun.rerun_status == "completed"
    fp = classify_alert(binding, suppression_history=["reviewed"])
    proposal = propose_suppression(classification=fp, rule_id=binding.rule_id)
    weak = propose_suppression(classification=classification, rule_id=binding.rule_id)
    assert proposal is not None and proposal.reviewer_required is True
    assert weak is None


def test_sarif_build_remaining_risk_and_reports(tmp_path) -> None:
    fixed = verify_sarif_delta(
        alert_id="a1", before_alerts=[NULL_ALERT], after_alerts=[]
    )
    remains = verify_sarif_delta(
        alert_id="a1", before_alerts=[NULL_ALERT], after_alerts=[NULL_ALERT]
    )
    blocked = verify_sarif_delta(
        alert_id="a1",
        before_alerts=[NULL_ALERT],
        after_alerts=[
            {
                "alert_id": "new",
                "rule_id": "CWE-89",
                "file_path": "src/db.py",
                "line": 1,
                "severity": "critical",
            }
        ],
    )
    sandbox = apply_patch_in_sandbox(
        patch=NullPatchGenerator().generate(
            build_repair_context(
                binding=bind_alert(NULL_ALERT, graph_snapshot_id="snap"),
                classification=classify_alert(
                    bind_alert(NULL_ALERT, graph_snapshot_id="snap")
                ),
                metadata=extract_predicate_metadata(bind_alert(NULL_ALERT)),
                examples=[],
            )
        ),
        workspace_root=tmp_path,
    )
    tests = run_build_and_tests(
        alert_id="a1", sandbox=sandbox, newly_failing_tests=["test_new"]
    )
    risk = make_remaining_risk_note(
        alert_id="a1",
        sarif=fixed,
        build_tests=tests,
        vulnerability_class=True,
        poc_plus_available=False,
    )
    clean_tests = run_build_and_tests(alert_id="a1", sandbox=sandbox)
    no_risk = make_remaining_risk_note(
        alert_id="a1",
        sarif=fixed,
        build_tests=clean_tests,
        vulnerability_class=False,
    )
    assert fixed.success is True
    assert remains.block_reason == "original_alert_remains"
    assert blocked.block_reason == "new_critical_or_error_alert"
    assert tests.test_run_status == "failed"
    assert risk.risk_level == "medium"
    assert no_risk.risk_level == "none"
    assert (
        run_sast_repair(alert=NULL_ALERT, sandbox_root=tmp_path).verdict
        == "alert_fixed_with_risk"
    )
    assert (
        run_sast_repair(
            alert=NULL_ALERT, sandbox_root=tmp_path, after_alerts=[NULL_ALERT]
        ).verdict
        == "repair_failed"
    )
    assert (
        run_sast_repair(
            alert=NULL_ALERT,
            sandbox_root=tmp_path,
            after_alerts=[
                {
                    "alert_id": "new",
                    "rule_id": "CWE-89",
                    "file_path": "src/db.py",
                    "line": 1,
                    "severity": "critical",
                }
            ],
        ).verdict
        == "repair_blocked"
    )
    assert (
        run_sast_repair(
            alert=NULL_ALERT,
            sandbox_root=tmp_path,
            suppression_history=["reviewed"],
            generate_patch=False,
        ).verdict
        == "false_positive_suppressed"
    )


def test_rule_evolution_stub() -> None:
    result = evolve_static_rules(ruleset="semgrep", sarif_deltas=["d1"])
    assert result["status"] == "not_implemented_in_phase_12"


@pytest.mark.asyncio
async def test_sast_repair_tools_and_template(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)
        examples = await handlers.get_predicate_examples(
            {"rule_id": "NULL_DEREF", "k": 1}
        )
        assert examples.payload["examples"][0]["rule_id"] == "NULL_DEREF"
        repair = await handlers.run_sast_repair(
            {"alert_id": "a1", "rule_id": "NULL_DEREF", "file_path": "src/app.py"}
        )
        assert repair.payload["report"]["harness_condition_id"].startswith("hcs:")
        queued = await handlers.run_sast_repair({"alert_id": "a1", "task": True})
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True
        evolution = await handlers.evolve_static_rules(
            {"ruleset": "semgrep", "sarif_deltas": ["d1"]}
        )
        assert evolution.payload["status"] == "not_implemented_in_phase_12"
        registry = PromptRegistry(SamplingCapability(status="unsupported"))
        register_default_prompts(registry)
        prompt = registry.get("sast-repair")
        assert "remaining-risk notes" in prompt["instructions"]
    finally:
        await context.close()
