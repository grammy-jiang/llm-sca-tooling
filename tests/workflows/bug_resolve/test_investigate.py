"""Tests for the investigate stage."""

from __future__ import annotations

from typing import Any

import pytest

from llm_sca_tooling.workflows.bug_resolve.investigate import run_investigate


async def test_null_localiser_with_nonempty_issue() -> None:
    result = await run_investigate(run_id="r1", issue_text="NPE in foo", null_mode=True)
    assert result.ranked_candidates
    assert result.top3_file_suspects == ["src/example.py"]
    assert result.confidence == "heuristic"


async def test_null_localiser_with_empty_issue() -> None:
    result = await run_investigate(run_id="r1", issue_text="", null_mode=True)
    assert result.ranked_candidates == []
    assert result.top3_file_suspects == []
    assert result.confidence == "unknown"


async def test_custom_localise_used() -> None:
    async def fake(issue: str, repos: list[str] | None) -> dict[str, Any]:
        return {
            "ranked_files": [
                {"file_path": "a.py", "score": 0.9},
                {"file_path": "b.py", "score": 0.5},
            ],
            "agreement_score": 0.8,
            "snapshot_id": "snap:1",
            "confidence": "analyser",
        }

    r = await run_investigate(run_id="r1", issue_text="hi", localise=fake)
    assert r.top3_file_suspects == ["a.py", "b.py"]
    assert r.agreement_score == pytest.approx(0.8)
    assert r.confidence == "analyser"


async def test_repo_qa_high_confidence_added_to_behavioural() -> None:
    async def fake_loc(issue: str, repos: list[str] | None) -> dict[str, Any]:
        return {
            "ranked_files": [{"file_path": "a.py", "score": 0.9}],
            "agreement_score": 0.5,
        }

    async def fake_qa(question: str, path: str) -> dict[str, Any]:
        return {"answer": "does X", "confidence": 0.8}

    r = await run_investigate(
        run_id="r1", issue_text="hi", localise=fake_loc, repo_qa=fake_qa
    )
    assert r.behavioural_context == ["does X"]


async def test_repo_qa_low_confidence_recorded_as_diagnostic() -> None:
    async def fake_loc(issue: str, repos: list[str] | None) -> dict[str, Any]:
        return {
            "ranked_files": [{"file_path": "a.py", "score": 0.9}],
            "agreement_score": 0.5,
        }

    async def fake_qa(question: str, path: str) -> dict[str, Any]:
        return {"answer": "maybe", "confidence": 0.1}

    r = await run_investigate(
        run_id="r1", issue_text="hi", localise=fake_loc, repo_qa=fake_qa
    )
    assert r.behavioural_context == []
    assert any(d.get("code") == "low_confidence_repo_qa" for d in r.diagnostics)


async def test_stale_snapshot_flag() -> None:
    async def fake(issue: str, repos: list[str] | None) -> dict[str, Any]:
        return {
            "ranked_files": [{"file_path": "a.py", "score": 0.9}],
            "snapshot_id": "snap:1",
        }

    r = await run_investigate(
        run_id="r1",
        issue_text="hi",
        localise=fake,
        expected_snapshot_id="snap:0",
    )
    assert r.stale_snapshot_flag is True
