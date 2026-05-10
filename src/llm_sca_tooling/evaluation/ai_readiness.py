"""AI-readiness report generator."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.models import AIReadinessReport


def generate_ai_readiness_report(
    repo_root: Path,
    *,
    repo_id: str,
    eval_run_id: str,
    harness_stage: str = "S3",
    previous: AIReadinessReport | None = None,
) -> AIReadinessReport:
    scores: dict[str, int] = {}
    findings: dict[str, list[str]] = {}
    scores["agent_config"], findings["agent_config"] = _score_agent_config(repo_root)
    scores["documentation"], findings["documentation"] = _score_documentation(repo_root)
    scores["ci_cd"], findings["ci_cd"] = _score_ci_cd(repo_root)
    scores["code_structure"], findings["code_structure"] = _score_code_structure(
        repo_root
    )
    scores["security"], findings["security"] = _score_security(repo_root)
    total = sum(scores.values())
    threshold = _stage_threshold(harness_stage)
    delta = None if previous is None else total - previous.total_score
    return AIReadinessReport(
        report_id=f"readiness:{eval_run_id.removeprefix('eval:')}",
        repo_id=repo_id,
        eval_run_id=eval_run_id,
        harness_stage=harness_stage,
        agent_config_score=scores["agent_config"],
        documentation_score=scores["documentation"],
        ci_cd_score=scores["ci_cd"],
        code_structure_score=scores["code_structure"],
        security_score=scores["security"],
        total_score=total,
        stage_threshold_met=total >= threshold
        and all(score >= _axis_floor(harness_stage) for score in scores.values()),
        axis_findings=findings,
        readiness_delta_from_last=delta,
        no_regression_check_pass=delta is None or delta >= 0,
    )


def _score_agent_config(root: Path) -> tuple[int, list[str]]:
    score = 0
    findings = []
    agents = root / "AGENTS.md"
    if agents.exists():
        score += 2
        text = agents.read_text(encoding="utf-8", errors="ignore")
        constraints = ("HC1", "HC2", "HC3", "HC4", "HC5", "HC6")
        if all(marker in text for marker in constraints):
            score += 2
        else:
            findings.append("hard constraint markers incomplete")
    else:
        findings.append("AGENTS.md missing")
    if (root / ".codex").exists() or (root / "CLAUDE.md").exists():
        score += 1
    return min(score, 5), findings


def _score_documentation(root: Path) -> tuple[int, list[str]]:
    checks = ["docs", "README.md", "Makefile", "pyproject.toml", ".agent/plan.md"]
    return _score_paths(root, checks)


def _score_ci_cd(root: Path) -> tuple[int, list[str]]:
    checks = [
        ".github/workflows",
        "tests",
        "pyproject.toml",
        ".pre-commit-config.yaml",
        "Makefile",
    ]
    return _score_paths(root, checks)


def _score_code_structure(root: Path) -> tuple[int, list[str]]:
    checks = ["src", "tests", ".importlinter", "schemas", "fixtures"]
    return _score_paths(root, checks)


def _score_security(root: Path) -> tuple[int, list[str]]:
    checks = [
        ".secrets.baseline",
        ".github/workflows",
        "pyproject.toml",
        "AGENTS.md",
        "schemas",
    ]
    return _score_paths(root, checks)


def _score_paths(root: Path, checks: list[str]) -> tuple[int, list[str]]:
    score = 0
    findings = []
    for relative in checks:
        if (root / relative).exists():
            score += 1
        else:
            findings.append(f"{relative} missing")
    return min(score, 5), findings


def _stage_threshold(stage: str) -> int:
    return {"S0": 0, "S1": 5, "S2": 12, "S3": 18}.get(stage, 18)


def _axis_floor(stage: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3}.get(stage, 3)
