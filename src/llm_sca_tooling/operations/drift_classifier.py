"""Harness-drift classifier.

Parses governance artefacts in a repository and classifies each as:
  - ``missing``      — required file does not exist
  - ``stale``        — file exists but does not reference the expected HC controls
  - ``relaxed``      — overlay widens permissions relative to AGENTS.md
  - ``out_of_stage`` — file exists but is not appropriate for the detected stage
  - ``clean``        — all checks pass for this file

Covered artefacts:
  1. AGENTS.md (authoritative governance manifest)
  2. CLAUDE.md (Claude Code overlay)
  3. .github/copilot-instructions.md (Copilot overlay)
  4. .codex/INSTRUCTIONS.md (Codex CLI overlay)
  5. .agents/skills/ (Agent Skills directories)
  6. .github/workflows/*.yml (CI pipeline)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["DriftFinding", "DriftReport", "classify_harness_drift"]

# HC controls that must appear in the authoritative AGENTS.md
_REQUIRED_HC_CONTROLS = {"HC1", "HC2", "HC3", "HC4", "HC5", "HC6"}

# Patterns that indicate permission widening in overlay files
_RELAXATION_PATTERNS = [
    re.compile(r"allow\s+all", re.IGNORECASE),
    re.compile(r"no\s+restrictions", re.IGNORECASE),
    re.compile(r"skip.*hc[1-6]", re.IGNORECASE),
    re.compile(r"disable.*constraint", re.IGNORECASE),
    re.compile(r"ignore.*hard\s+constraint", re.IGNORECASE),
]


@dataclass
class DriftFinding:
    artefact: str
    status: str  # missing | stale | relaxed | out_of_stage | clean
    details: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass
class DriftReport:
    repo_root: str
    findings: list[DriftFinding] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return any(f.status != "clean" for f in self.findings)

    @property
    def drift_count(self) -> int:
        return sum(1 for f in self.findings if f.status != "clean")


def classify_harness_drift(repo_root: str) -> DriftReport:
    """Classify harness drift for all governance artefacts in *repo_root*."""
    root = Path(repo_root).resolve()
    report = DriftReport(repo_root=str(root))

    agents_content = _check_agents_md(root, report)
    _check_overlay(
        root / "CLAUDE.md",
        "CLAUDE.md",
        agents_content,
        report,
        required=False,
    )
    _check_overlay(
        root / ".github" / "copilot-instructions.md",
        ".github/copilot-instructions.md",
        agents_content,
        report,
        required=False,
    )
    _check_overlay(
        root / ".codex" / "INSTRUCTIONS.md",
        ".codex/INSTRUCTIONS.md",
        agents_content,
        report,
        required=False,
    )
    _check_skills(root, report)
    _check_ci(root, report)

    return report


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _check_agents_md(root: Path, report: DriftReport) -> str:
    """Check AGENTS.md for all HC control references. Return its content."""
    path = root / "AGENTS.md"
    content = _read_text(path)
    if content is None:
        report.findings.append(
            DriftFinding(
                artefact="AGENTS.md",
                status="missing",
                details="AGENTS.md is the authoritative governance manifest and is required.",
            )
        )
        return ""

    missing_hc = [hc for hc in sorted(_REQUIRED_HC_CONTROLS) if hc not in content]
    if missing_hc:
        report.findings.append(
            DriftFinding(
                artefact="AGENTS.md",
                status="stale",
                details=f"Missing HC control references: {', '.join(missing_hc)}",
                evidence=missing_hc,
            )
        )
    else:
        report.findings.append(DriftFinding(artefact="AGENTS.md", status="clean"))
    return content


def _check_overlay(
    path: Path,
    label: str,
    agents_content: str,
    report: DriftReport,
    *,
    required: bool,
) -> None:
    """Check an overlay file for relaxation patterns."""
    content = _read_text(path)
    if content is None:
        if required:
            report.findings.append(
                DriftFinding(
                    artefact=label,
                    status="missing",
                    details=f"{label} is required but does not exist.",
                )
            )
        # Not required — absence is fine, skip
        return

    # Check for explicit relaxation
    relaxed_lines: list[str] = []
    for pattern in _RELAXATION_PATTERNS:
        for i, line in enumerate(content.splitlines(), start=1):
            if pattern.search(line):
                relaxed_lines.append(f"line {i}: {line.strip()}")

    if relaxed_lines:
        report.findings.append(
            DriftFinding(
                artefact=label,
                status="relaxed",
                details=(
                    f"Overlay {label!r} contains patterns that may widen permissions."
                ),
                evidence=relaxed_lines[:5],
            )
        )
        return

    if (
        agents_content
        and "HC" not in content
        and "hard constraint" not in content.lower()
        and re.search(r"allow|deny|permission|tool|mode", content, re.IGNORECASE)
    ):
        report.findings.append(
            DriftFinding(
                artefact=label,
                status="stale",
                details=(
                    f"Overlay {label!r} references permissions but does not"
                    " reference HC controls."
                ),
            )
        )
        return

    report.findings.append(DriftFinding(artefact=label, status="clean"))


def _check_skills(root: Path, report: DriftReport) -> None:
    """Check .agents/skills/ for SKILL.md presence in each skill directory."""
    skills_dir = root / ".agents" / "skills"
    if not skills_dir.is_dir():
        # Skills are optional — only flag if there's a skills section in AGENTS.md
        agents_path = root / "AGENTS.md"
        agents_content = _read_text(agents_path) or ""
        if ".agents/skills" in agents_content:
            report.findings.append(
                DriftFinding(
                    artefact=".agents/skills/",
                    status="missing",
                    details=(
                        "AGENTS.md references .agents/skills/ but the directory does"
                        " not exist."
                    ),
                )
            )
        return

    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                report.findings.append(
                    DriftFinding(
                        artefact=f".agents/skills/{skill_dir.name}/SKILL.md",
                        status="missing",
                        details=f"Skill directory {skill_dir.name!r} lacks SKILL.md.",
                    )
                )
            else:
                report.findings.append(
                    DriftFinding(
                        artefact=f".agents/skills/{skill_dir.name}/SKILL.md",
                        status="clean",
                    )
                )


def _check_ci(root: Path, report: DriftReport) -> None:
    """Check .github/workflows/ for at least one CI workflow."""
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        report.findings.append(
            DriftFinding(
                artefact=".github/workflows/",
                status="missing",
                details=("No .github/workflows/ directory; no CI pipeline detected."),
            )
        )
        return

    workflow_files = list(workflows_dir.glob("*.yml")) + list(
        workflows_dir.glob("*.yaml")
    )
    if not workflow_files:
        report.findings.append(
            DriftFinding(
                artefact=".github/workflows/",
                status="stale",
                details="CI workflows directory exists but contains no YAML files.",
            )
        )
    else:
        report.findings.append(
            DriftFinding(
                artefact=".github/workflows/",
                status="clean",
                details=f"{len(workflow_files)} workflow file(s) found.",
            )
        )
