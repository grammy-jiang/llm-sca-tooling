from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.fl.investigate import InvestigateBudget, render_investigate_prompt
from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.memory_stub import MemoryHintStub
from llm_sca_tooling.fl.sbfl import ochiai, parse_lcov


def test_ochiai_formula() -> None:
    assert round(ochiai(3, 1, 0, 3), 6) == 0.866025


def test_lcov_parser(tmp_path: Path) -> None:
    lcov = tmp_path / "lcov.info"
    lcov.write_text(
        "TN:\nSF:/repo/src/pkg/core.py\nDA:1,1\nDA:2,0\nend_of_record\n",
        encoding="utf-8",
    )

    records = parse_lcov(lcov, snapshot_id="snapshot:test")

    assert records[0].file_path == "src/pkg/core.py"
    assert records[0].line_coverage == {1: 1, 2: 0}


def test_memory_stub_returns_empty_hints() -> None:
    issue = normalize_issue_text("KeyError in validate")

    result = MemoryHintStub().retrieve_fl_hints(issue, max_hints=5)

    assert result.hints_used == []
    assert result.hints_rejected == []
    assert result.misalignment_guard_applied


def test_investigate_prompt_template_renders() -> None:
    prompt = render_investigate_prompt(
        "src/llm_sca_tooling/mcp_server/prompts/investigate.md",
        issue_text_normalized="keyerror in validate",
        repos=["repo:demo"],
        budget=InvestigateBudget(),
        context_bundle_summary="src/pkg/core.py",
        ranked_candidates_with_signals="1. src/pkg/core.py keyword=1.0",
    )

    assert "keyerror in validate" in prompt
    assert "src/pkg/core.py" in prompt
    assert "{issue_text_normalized}" not in prompt
