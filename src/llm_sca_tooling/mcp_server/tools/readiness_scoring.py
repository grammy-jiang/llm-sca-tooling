"""Shared deterministic readiness scoring for MCP readiness tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from llm_sca_tooling.hardening.harness_drift import HarnessDriftChecker
from llm_sca_tooling.hardening.models import DriftClassification


@dataclass(frozen=True)
class ReadinessSnapshot:
    root: Path
    axis_scores: dict[str, int]
    harness_stage: str
    drift_findings: list[str]
    missing_gates: list[str]
    absent_scanners: list[str]
    recommended_tasks: list[str]

    @property
    def total_score(self) -> int:
        return sum(self.axis_scores.values())


def compute_readiness_snapshot(repo: str) -> ReadinessSnapshot:
    root = Path(repo)
    scores: dict[str, int] = {
        "agent_config": 0,
        "documentation": 0,
        "ci_cd": 0,
        "code_structure": 0,
        "security": 0,
    }

    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        scores["agent_config"] += 2
        if "HC1" in agents_md.read_text(encoding="utf-8", errors="replace"):
            scores["agent_config"] += 1
    if (root / "CLAUDE.md").exists():
        scores["agent_config"] += 1
    if (root / ".agent" / "harness-stage.json").exists():
        scores["agent_config"] += 1
    scores["agent_config"] = min(5, scores["agent_config"])

    docs = root / "docs"
    if docs.is_dir():
        doc_count = len(list(docs.glob("*.md")))
        scores["documentation"] = min(5, max(0, doc_count // 3))

    workflows = root / ".github" / "workflows"
    workflow_files = []
    if workflows.is_dir():
        workflow_files = list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))
        scores["ci_cd"] = min(5, len(workflow_files))

    has_src = (root / "src").is_dir()
    has_tests = (root / "tests").is_dir()
    has_pyproject = (root / "pyproject.toml").exists()
    scores["code_structure"] = min(
        5,
        sum([has_src, has_tests, has_pyproject]) + (2 if has_src and has_tests else 0),
    )

    absent_scanners: list[str] = []
    if (root / ".secrets.baseline").exists():
        scores["security"] += 2
    else:
        absent_scanners.append("detect-secrets")
    if (root / ".pre-commit-config.yaml").exists():
        scores["security"] += 1
    else:
        absent_scanners.append("pre-commit")
    if any(
        "bandit" in path.read_text(encoding="utf-8", errors="replace").lower()
        or "sast" in path.name.lower()
        for path in workflow_files
    ):
        scores["security"] += 2
    else:
        absent_scanners.append("sast-workflow")
    scores["security"] = min(5, scores["security"])

    drift_records = HarnessDriftChecker().check_repo(root)
    drift_findings = [
        r.detail or r.classification.value
        for r in drift_records
        if r.classification != DriftClassification.CLEAN
    ]
    missing_gates: list[str] = []
    if any(r.classification == DriftClassification.RELAXED for r in drift_records):
        missing_gates.append("relaxed-drift-blocks-release")
    if any(r.classification == DriftClassification.MISSING for r in drift_records):
        missing_gates.append("missing-harness-artifacts")

    stage = "S3"
    stage_path = root / ".agent" / "harness-stage.json"
    if stage_path.exists():
        try:
            stage = str(
                json.loads(stage_path.read_text(encoding="utf-8")).get("stage", "S3")
            )
        except (OSError, json.JSONDecodeError, TypeError):
            stage = "S3"

    tasks = [
        f"Fix {r.classification.value} drift in {r.artifact_path}"
        for r in drift_records
        if r.classification != DriftClassification.CLEAN
    ]
    tasks.extend(f"Enable {scanner}" for scanner in absent_scanners)

    return ReadinessSnapshot(
        root=root,
        axis_scores=scores,
        harness_stage=stage,
        drift_findings=drift_findings,
        missing_gates=missing_gates,
        absent_scanners=absent_scanners,
        recommended_tasks=tasks,
    )
