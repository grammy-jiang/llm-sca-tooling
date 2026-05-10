"""Tests for the bug-resolve prompt file."""

from __future__ import annotations

from pathlib import Path

PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "src/llm_sca_tooling/mcp_server/prompts/bug_resolve.md"
)


def test_prompt_exists() -> None:
    assert PROMPT_PATH.exists()


def test_prompt_mentions_run_issue_resolution() -> None:
    text = PROMPT_PATH.read_text()
    assert "run_issue_resolution" in text


def test_prompt_mentions_ten_stages() -> None:
    text = PROMPT_PATH.read_text()
    for stage in (
        "load",
        "investigate",
        "repair",
        "dryrun",
        "gates",
        "patch_risk",
        "blast_radius",
        "scope_audit",
        "operational_review",
        "trajectory",
    ):
        assert stage in text, stage


def test_prompt_mentions_merge_supporting() -> None:
    text = PROMPT_PATH.read_text()
    assert "merge-supporting" in text
