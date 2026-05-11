"""AI-readiness report generation."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.models import AIReadinessReport

__all__ = ["generate_ai_readiness_report"]


def generate_ai_readiness_report(
    *,
    repo_root: Path,
    repo_id: str,
    eval_run_id: str,
    previous_total_score: int | None = None,
) -> AIReadinessReport:
    scores = {
        "agent_config": 5 if (repo_root / "AGENTS.md").exists() else 0,
        "documentation": (
            min(5, len(list((repo_root / "docs").glob("*.md"))) // 2)
            if (repo_root / "docs").exists()
            else 0
        ),
        "ci_cd": 4 if (repo_root / "Makefile").exists() else 1,
        "code_structure": (
            4 if (repo_root / "src").exists() and (repo_root / "tests").exists() else 1
        ),
        "security": 4 if (repo_root / "pyproject.toml").exists() else 1,
    }
    total = sum(scores.values())
    threshold = total >= 18 and min(scores.values()) >= 3
    delta = total - previous_total_score if previous_total_score is not None else 0
    findings = {axis: f"score={score}" for axis, score in scores.items()}
    return AIReadinessReport(
        report_id=f"ai-ready:{eval_run_id}",
        repo_id=repo_id,
        eval_run_id=eval_run_id,
        harness_stage="S3" if threshold else "S2",
        agent_config_score=scores["agent_config"],
        documentation_score=scores["documentation"],
        ci_cd_score=scores["ci_cd"],
        code_structure_score=scores["code_structure"],
        security_score=scores["security"],
        total_score=total,
        stage_threshold_met=threshold,
        axis_findings=findings,
        readiness_delta_from_last=delta,
        no_regression_check_pass=delta >= 0,
    )
