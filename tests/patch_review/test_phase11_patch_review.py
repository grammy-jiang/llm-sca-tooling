from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.sampling import SamplingCapability
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.patch_review.ast_diff import extract_ast_diff_features
from llm_sca_tooling.patch_review.diff_parser import parse_diff
from llm_sca_tooling.patch_review.dryrun import (
    compare_dryrun_actual,
    make_dryrun_prediction,
)
from llm_sca_tooling.patch_review.four_agent_audit import run_four_axis_audit
from llm_sca_tooling.patch_review.graph_context import extract_graph_context
from llm_sca_tooling.patch_review.interface_compat import check_interface_compatibility
from llm_sca_tooling.patch_review.maintainability_gate import run_maintainability_gate
from llm_sca_tooling.patch_review.merge_policy import recommend_merge
from llm_sca_tooling.patch_review.models import DiffRecord, PolicyAction, RiskClass
from llm_sca_tooling.patch_review.operational_integration import (
    integrate_operational_result,
)
from llm_sca_tooling.patch_review.report import run_patch_review
from llm_sca_tooling.patch_review.risk_classifier import classify_patch_risk
from llm_sca_tooling.patch_review.risk_policy import apply_deterministic_policy
from llm_sca_tooling.patch_review.sarif_delta import compute_sarif_delta
from llm_sca_tooling.patch_review.scope_audit import audit_scope
from llm_sca_tooling.patch_review.symbol_detector import detect_changed_symbols
from llm_sca_tooling.patch_review.test_delta import compute_test_delta

SAFE_DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,3 @@
 def fix(x):
-    return x
+    if x is None:
+        return ""
+    return x
"""

API_DIFF = """diff --git a/src/api/routes.py b/src/api/routes.py
--- a/src/api/routes.py
+++ b/src/api/routes.py
@@ -1,2 +1,2 @@
-def api_get_user(id):
+def api_get_user(id, required):
     return id
"""

BAD_SCOPE_DIFF = """diff --git a/secrets/token.txt b/secrets/token.txt
--- a/secrets/token.txt
+++ b/secrets/token.txt
@@ -1 +1 @@
-old
+new
"""


def test_models_parse_and_validate() -> None:
    diff = parse_diff(SAFE_DIFF, snapshot_before_id="old", snapshot_after_id="new")
    assert diff.changed_files == ["src/app.py"]
    assert diff.added_lines == 3
    assert DiffRecord.model_validate_json(diff.model_dump_json()) == diff
    with pytest.raises(ValidationError):
        DiffRecord.model_validate({"diff_id": "d"})


def test_symbol_ast_and_graph_features() -> None:
    diff = parse_diff(API_DIFF)
    symbols = detect_changed_symbols(diff)
    assert symbols[0].is_interface_boundary is True
    assert symbols[0].change_kind == "modified_signature"
    ast = extract_ast_diff_features(diff, symbols)
    graph = extract_graph_context(diff_id=diff.diff_id, symbols=symbols)
    assert ast.signature_changed is True
    assert ast.edit_operation == "signature_change"
    loop_ast = extract_ast_diff_features(
        parse_diff("+++ b/src/x.py\n@@ -1 +1 @@\n-old\n+for item in items:\n"),
        symbols,
    )
    raise_ast = extract_ast_diff_features(
        parse_diff("+++ b/src/x.py\n@@ -1 +1 @@\n-old\n+raise ValueError()\n"),
        symbols,
    )
    assert loop_ast.edit_operation == "loop_inserted"
    assert raise_ast.raises_new_exception is True
    assert graph.interface_boundary_nodes
    generated = parse_diff("+++ b/src/generated_stub.py\n@@ -1 +1 @@\n-old\n+new\n")
    assert detect_changed_symbols(generated)[0].is_generated is True
    added_only = parse_diff("+++ b/src/new.py\n@@ -0,0 +1 @@\n+def new(): pass\n")
    removed_only = parse_diff("+++ b/src/old.py\n@@ -1 +0,0 @@\n-def old(): pass\n")
    doc = parse_diff('+++ b/src/doc.py\n@@ -1 +1 @@\n-"""old"""\n+"""new"""\n')
    assert detect_changed_symbols(added_only)[0].change_kind == "added"
    assert detect_changed_symbols(removed_only)[0].change_kind == "removed"
    assert detect_changed_symbols(doc)[0].change_kind == "modified_docstring"
    empty = parse_diff("not a diff")
    assert detect_changed_symbols(empty)[0].confidence == "unknown"


def test_sarif_test_delta_and_interface_compatibility() -> None:
    sarif = compute_sarif_delta(
        diff_id="d",
        before=[],
        after=[
            {
                "rule_id": "CWE-79",
                "file_path": "src/app.py",
                "line": 1,
                "message": "xss",
                "severity": "critical",
            }
        ],
    )
    assert sarif.has_new_critical is True
    assert sarif.has_new_security is True
    fixed = compute_sarif_delta(
        diff_id="d",
        before=[{"rule_id": "R", "file_path": "a", "line": 1, "message": "m"}],
        after=[],
    )
    assert fixed.fixed_alerts
    tests = compute_test_delta(
        diff_id="d",
        before_failed=["old"],
        after_failed=["new"],
        before_passed=["keep"],
        after_passed=["keep"],
        poc_plus_result="failed",
    )
    assert tests.newly_failing == ["new"]
    assert tests.newly_passing == ["old"]
    assert check_interface_compatibility(parse_diff(API_DIFF)).breaking_changes
    candidate = check_interface_compatibility(
        parse_diff("+++ b/src/api/routes.py\n@@ -1 +1 @@\n-old\n+new\n")
    )
    assert candidate.candidate_changes == ["interface file changed"]


def test_dryrun_scope_maintainability_and_operational() -> None:
    diff = parse_diff(SAFE_DIFF)
    prediction = make_dryrun_prediction(diff)
    mismatch = compare_dryrun_actual(
        prediction, actual_files_changed=["src/app.py", "src/extra.py"]
    )
    fewer = compare_dryrun_actual(prediction, actual_files_changed=[])
    assert mismatch[0].mismatch_type == "extra_files_changed"
    assert fewer[0].mismatch_type == "fewer_files_changed"
    scope = audit_scope(changed_paths=["README.md"], run_events=["tool_call"])
    assert scope.out_of_scope_writes == ["README.md"]
    assert scope.process_verdict == "process-noncompliant"
    incomplete = audit_scope(changed_paths=["src/app.py"], run_events=["tool_call"])
    assert incomplete.process_verdict == "trace-incomplete"
    maintainability = run_maintainability_gate(parse_diff(SAFE_DIFF))
    assert maintainability.overall_pass is True
    operational = integrate_operational_result(incomplete)
    blocked_operational = integrate_operational_result(scope)
    assert operational.operational_recommendation == PolicyAction.review_required
    assert blocked_operational.operational_recommendation == PolicyAction.block


def test_risk_classifier_block_conditions_and_unknown() -> None:
    safe, vector, context = classify_patch_risk(diff_text=SAFE_DIFF)
    assert safe.risk_class == RiskClass.safe
    assert safe.policy_action == PolicyAction.merge_supporting
    assert vector.maintainability_gate_pass is True
    assert context["dryrun"].expected_files_changed == ["src/app.py"]
    sarif_risk, _, _ = classify_patch_risk(
        diff_text=SAFE_DIFF,
        sarif_after=[
            {
                "rule_id": "CWE-89",
                "file_path": "src/app.py",
                "line": 1,
                "message": "injection",
                "severity": "error",
            }
        ],
    )
    assert sarif_risk.policy_action == PolicyAction.block
    failing, _, _ = classify_patch_risk(
        diff_text=SAFE_DIFF, after_failed=["test_required"]
    )
    assert failing.risk_class == RiskClass.correct_but_overfit
    scope, _, _ = classify_patch_risk(diff_text=BAD_SCOPE_DIFF)
    assert scope.policy_action == PolicyAction.block
    unknown, _, _ = classify_patch_risk(
        diff_text=API_DIFF, run_events=["tool_call", "gate_result"]
    )
    assert unknown.risk_class == RiskClass.unknown


def test_four_axis_review_report_and_merge_policy() -> None:
    risk, _, _ = classify_patch_risk(diff_text=SAFE_DIFF)
    axes = run_four_axis_audit(
        risk=risk, evidence_ref="memory://e", sampling_supported=True
    )
    assert set(axes) == {"correctness", "security", "performance", "compatibility"}
    assert all(axis.sampling_used for axis in axes.values())
    report = run_patch_review(diff_text=SAFE_DIFF, sampling_supported=False)
    assert report.recommendation == PolicyAction.merge_supporting
    assert report.fallback_mode is True
    blocked = run_patch_review(
        diff_text=SAFE_DIFF,
        sarif_after=[
            {
                "rule_id": "CWE-79",
                "file_path": "src/app.py",
                "line": 1,
                "message": "xss",
                "severity": "critical",
            }
        ],
    )
    assert blocked.recommendation == PolicyAction.block
    interface_risk, _, _ = classify_patch_risk(diff_text=API_DIFF)
    interface_axes = run_four_axis_audit(
        risk=interface_risk, evidence_ref="memory://e", sampling_supported=False
    )
    assert interface_axes["compatibility"].findings
    failing_risk, _, _ = classify_patch_risk(diff_text=SAFE_DIFF, after_failed=["test"])
    failing_axes = run_four_axis_audit(
        risk=failing_risk, evidence_ref="memory://e", sampling_supported=False
    )
    assert failing_axes["correctness"].findings
    operational = integrate_operational_result(
        audit_scope(changed_paths=["src/app.py"])
    )
    assert (
        recommend_merge(risk=risk, operational=operational)
        == PolicyAction.merge_supporting
    )
    unknown_risk, _, _ = classify_patch_risk(
        diff_text=SAFE_DIFF, run_events=["tool_call", "gate_result"]
    )
    assert (
        recommend_merge(risk=unknown_risk, operational=operational)
        == PolicyAction.review_required
    )


def test_remaining_policy_branches() -> None:
    maintainability_risk, _, _ = classify_patch_risk(
        diff_text=(
            "+++ b/src/other.py\n@@ -1 +1 @@\n"
            "-old\n+import llm_sca_tooling.evaluation\n"
        )
    )
    budget_risk, _, _ = classify_patch_risk(
        diff_text=SAFE_DIFF,
        run_events=["tool_call", "gate_result", "budget_event", "budget_hard_stop"],
    )
    _poc_risk, vector, context = classify_patch_risk(diff_text=SAFE_DIFF)
    context["test_delta"].poc_plus_result = "failed"
    poc = apply_deterministic_policy(
        feature_vector=vector,
        sarif_delta=context["sarif_delta"],
        test_delta=context["test_delta"],
        interface=context["interface"],
        scope=context["scope"],
        maintainability=context["maintainability"],
    )
    assert "maintainability-gate" in maintainability_risk.active_overrides
    assert budget_risk.policy_action == PolicyAction.review_required
    assert poc.risk_class == RiskClass.vulnerable


@pytest.mark.asyncio
async def test_patch_review_tools_and_templates(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(
        config, client_capabilities={"sampling": {"maxTokens": 1000}}
    )
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)
        classified = await handlers.classify_patch_risk({"diff": SAFE_DIFF})
        assert classified.payload["risk"]["risk_class"] == "safe"
        blocked = await handlers.run_patch_review(
            {
                "diff": SAFE_DIFF,
                "sarif_after": [
                    {
                        "rule_id": "CWE-79",
                        "file_path": "src/app.py",
                        "line": 1,
                        "message": "xss",
                        "severity": "critical",
                    }
                ],
            }
        )
        assert blocked.payload["report"]["recommendation"] == "block"
        queued = await handlers.run_patch_review({"diff": SAFE_DIFF, "task": True})
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True
        registry = PromptRegistry(SamplingCapability(status="supported"))
        register_default_prompts(registry)
        audit_prompt = registry.get("audit")
        risk_prompt = registry.get("risk-classify")
        assert "deterministic block condition" in audit_prompt["instructions"]
        assert "calibration family" in risk_prompt["instructions"]
    finally:
        await context.close()
