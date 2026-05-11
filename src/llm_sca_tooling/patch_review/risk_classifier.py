"""Patch-risk classifier interface and deterministic implementation."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.ast_diff import extract_ast_diff_features
from llm_sca_tooling.patch_review.diff_parser import parse_diff
from llm_sca_tooling.patch_review.dryrun import (
    compare_dryrun_actual,
    make_dryrun_prediction,
)
from llm_sca_tooling.patch_review.graph_context import extract_graph_context
from llm_sca_tooling.patch_review.interface_compat import check_interface_compatibility
from llm_sca_tooling.patch_review.maintainability_gate import run_maintainability_gate
from llm_sca_tooling.patch_review.models import PatchRiskFeatureVector, PatchRiskResult
from llm_sca_tooling.patch_review.risk_features import assemble_feature_vector
from llm_sca_tooling.patch_review.risk_policy import apply_deterministic_policy
from llm_sca_tooling.patch_review.sarif_delta import compute_sarif_delta
from llm_sca_tooling.patch_review.scope_audit import audit_scope
from llm_sca_tooling.patch_review.symbol_detector import detect_changed_symbols
from llm_sca_tooling.patch_review.test_delta import compute_test_delta


class RiskClassificationBundle(tuple[PatchRiskResult, PatchRiskFeatureVector]):
    pass


def classify_patch_risk(
    *,
    diff_text: str,
    sarif_before: list[dict[str, Any]] | None = None,
    sarif_after: list[dict[str, Any]] | None = None,
    before_failed: list[str] | None = None,
    after_failed: list[str] | None = None,
    run_events: list[str] | None = None,
    run_id: str | None = None,
    snapshot_before: str | None = None,
    snapshot_after: str | None = None,
) -> tuple[PatchRiskResult, PatchRiskFeatureVector, dict[str, Any]]:
    diff = parse_diff(
        diff_text,
        snapshot_before_id=snapshot_before,
        snapshot_after_id=snapshot_after,
    )
    symbols = detect_changed_symbols(diff)
    ast_features = extract_ast_diff_features(diff, symbols)
    graph = extract_graph_context(
        diff_id=diff.diff_id, symbols=symbols, snapshot_id=snapshot_after
    )
    sarif = compute_sarif_delta(
        diff_id=diff.diff_id, before=sarif_before, after=sarif_after
    )
    tests = compute_test_delta(
        diff_id=diff.diff_id,
        before_failed=before_failed,
        after_failed=after_failed,
    )
    interface = check_interface_compatibility(diff)
    dryrun = make_dryrun_prediction(diff)
    mismatches = compare_dryrun_actual(dryrun, actual_files_changed=diff.changed_files)
    scope = audit_scope(
        changed_paths=diff.changed_files, run_id=run_id, run_events=run_events
    )
    maintainability = run_maintainability_gate(diff)
    vector = assemble_feature_vector(
        diff_id=diff.diff_id,
        ast_features=ast_features,
        interface=interface,
        scope=scope,
        maintainability=maintainability,
        dryrun_mismatch_count=len(mismatches),
    )
    risk = apply_deterministic_policy(
        feature_vector=vector,
        sarif_delta=sarif,
        test_delta=tests,
        interface=interface,
        scope=scope,
        maintainability=maintainability,
    )
    context = {
        "diff": diff,
        "symbols": symbols,
        "ast_features": ast_features,
        "graph_context": graph,
        "sarif_delta": sarif,
        "test_delta": tests,
        "interface": interface,
        "dryrun": dryrun,
        "dryrun_mismatches": mismatches,
        "scope": scope,
        "maintainability": maintainability,
    }
    return risk, vector, context
