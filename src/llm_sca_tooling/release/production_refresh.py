"""Production-derived evaluation refresh workflow."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.release.models import ProductionEvalRefreshRecord

__all__ = ["build_refresh_record", "convert_refresh_to_benchmark_instance"]


def build_refresh_record(
    *,
    source_run_id: str,
    issue_text: str,
    repo_id: str,
    fail_to_pass_tests_present: bool,
    pass_to_pass_tests_present: bool,
    test_relevance_validated: bool,
    flaky_flag: bool,
    approved: bool = False,
    added_to_suite_id: str | None = None,
) -> ProductionEvalRefreshRecord:
    issue_hash = hashlib.sha256(issue_text.encode("utf-8")).hexdigest()
    return ProductionEvalRefreshRecord(
        source_run_id=source_run_id,
        issue_text_hash=issue_hash,
        repo_id=repo_id,
        gold_patch_hidden=True,
        fail_to_pass_tests_present=fail_to_pass_tests_present,
        pass_to_pass_tests_present=pass_to_pass_tests_present,
        test_relevance_validated=test_relevance_validated,
        flaky_flag=flaky_flag,
        approved=approved,
        added_to_suite_id=added_to_suite_id,
    )


def convert_refresh_to_benchmark_instance(
    record: ProductionEvalRefreshRecord,
) -> dict[str, str]:
    if not record.approved:
        raise ValueError("human approval is required before suite inclusion")
    if not record.gold_patch_hidden:
        raise ValueError("gold patch must be hidden")
    if not record.fail_to_pass_tests_present:
        raise ValueError("fail-to-pass tests are required")
    if not record.test_relevance_validated:
        raise ValueError("test relevance must be validated")
    if record.flaky_flag:
        raise ValueError("flaky instances are excluded")
    return {
        "instance_id": record.refresh_id.replace("refresh:", "prod-refresh:"),
        "repo_id": record.repo_id,
        "issue_text_hash": record.issue_text_hash,
        "suite_id": record.added_to_suite_id or "production-refresh",
        "gold_patch_ref": "hidden",
    }
