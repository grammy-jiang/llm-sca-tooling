from __future__ import annotations

from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.keyword_retrieval import KeywordRetriever


def test_keyword_retrieval_ranks_stack_trace_file_first(fl_workspace, fl_repo) -> None:
    issue = normalize_issue_text("""
Traceback (most recent call last):
  File "/tmp/repo/src/pkg/core.py", line 3, in validate
KeyError: 'name' in UserService.validate
""")

    candidates = KeywordRetriever(fl_workspace.graph).retrieve(
        issue, repo_ids=[fl_repo.repo_id]
    )

    assert candidates
    assert candidates[0].file_path == "src/pkg/core.py"
    assert candidates[0].signals[0].raw_score >= 0.5
    assert "stack frame file" in candidates[0].signals[0].evidence


def test_keyword_retrieval_returns_empty_for_no_matches(fl_workspace, fl_repo) -> None:
    issue = normalize_issue_text("completely unrelated prose without code identifiers")

    assert (
        KeywordRetriever(fl_workspace.graph).retrieve(issue, repo_ids=[fl_repo.repo_id])
        == []
    )
