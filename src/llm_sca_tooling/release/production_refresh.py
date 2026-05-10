"""Production-derived eval refresh workflow."""

from __future__ import annotations

import uuid

from llm_sca_tooling.release.models import ProductionEvalRefreshRecord


def build_production_refresh_record(
    *,
    source_run_id: str,
    issue_text_hash: str,
    repo_id: str,
    fail_to_pass_tests_present: bool,
    pass_to_pass_tests_present: bool,
    test_relevance_validated: bool,
    flaky_flag: bool,
    approved: bool,
    suite_id: str,
) -> ProductionEvalRefreshRecord:
    added = (
        suite_id
        if approved
        and fail_to_pass_tests_present
        and test_relevance_validated
        and not flaky_flag
        else None
    )
    return ProductionEvalRefreshRecord(
        refresh_id=f"refresh:{uuid.uuid4().hex}",
        source_run_id=source_run_id,
        issue_text_hash=issue_text_hash,
        repo_id=repo_id,
        gold_patch_hidden=True,
        fail_to_pass_tests_present=fail_to_pass_tests_present,
        pass_to_pass_tests_present=pass_to_pass_tests_present,
        test_relevance_validated=test_relevance_validated,
        flaky_flag=flaky_flag,
        approved=approved,
        added_to_suite_id=added,
    )
