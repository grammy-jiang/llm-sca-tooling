"""Full Phase 18 readiness-audit launcher."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.evaluation.ai_readiness import generate_ai_readiness_report
from llm_sca_tooling.release.models import ReadinessAuditReport

__all__ = ["run_readiness_audit"]


def run_readiness_audit(
    *,
    repo: str | Path,
    policy: str | None = None,
    task: str | None = None,
) -> ReadinessAuditReport:
    del policy, task
    repo_root = Path(repo)
    report = generate_ai_readiness_report(
        repo_root=repo_root,
        repo_id=repo_root.name or "repo",
        eval_run_id="eval:readiness-audit",
    )
    missing_gates = _missing_gates(repo_root)
    absent_scanners = _absent_scanners(repo_root)
    recommendations = [
        f"Add or repair {item}." for item in [*missing_gates, *absent_scanners]
    ]
    return ReadinessAuditReport(
        repo=str(repo_root),
        ai_readiness_score=report.total_score,
        harness_stage=report.harness_stage,
        drift_findings=_drift_findings(repo_root),
        missing_gates=missing_gates,
        weak_docs_spec_links=_weak_docs(repo_root),
        unprotected_risky_paths=_unprotected_paths(repo_root),
        absent_scanners=absent_scanners,
        recommended_readiness_tasks=recommendations,
        ai_readiness_report_ref=report.report_id,
    )


def _missing_gates(repo_root: Path) -> list[str]:
    checks = {
        "make verify": repo_root / "Makefile",
        "unit tests": repo_root / "tests",
        "pyproject config": repo_root / "pyproject.toml",
        "harness manifest": repo_root / "AGENTS.md",
    }
    return [name for name, path in checks.items() if not path.exists()]


def _absent_scanners(repo_root: Path) -> list[str]:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return ["ruff", "mypy", "detect-secrets", "bandit", "pip-audit"]
    text = pyproject.read_text(encoding="utf-8")
    return [
        scanner
        for scanner in ["ruff", "mypy", "detect-secrets", "bandit", "pip-audit"]
        if scanner not in text
    ]


def _drift_findings(repo_root: Path) -> list[str]:
    findings: list[str] = []
    agents = repo_root / "AGENTS.md"
    codex = repo_root / ".codex" / "INSTRUCTIONS.md"
    if (
        agents.exists()
        and codex.exists()
        and "HC1" not in codex.read_text(encoding="utf-8")
    ):
        findings.append(".codex/INSTRUCTIONS.md does not restate HC controls")
    return findings


def _weak_docs(repo_root: Path) -> list[str]:
    docs = repo_root / "docs"
    if not docs.exists():
        return ["docs directory missing"]
    linked_specs = list(docs.glob("*implementation-plan*.md"))
    return [] if linked_specs else ["implementation plan links missing"]


def _unprotected_paths(repo_root: Path) -> list[str]:
    risky = [repo_root / ".github" / "workflows", repo_root / ".pre-commit-config.yaml"]
    return [str(path.relative_to(repo_root)) for path in risky if not path.exists()]
