"""Tests for Phase 13 skill templates."""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[3] / ".skills"


def test_investigate_skill() -> None:
    p = SKILLS_DIR / "investigate.SKILL.md"
    assert p.exists()
    txt = p.read_text()
    assert "get_relevant_files" in txt


def test_repair_skill() -> None:
    p = SKILLS_DIR / "repair.SKILL.md"
    assert p.exists()
    txt = p.read_text()
    assert "run_sast_repair" in txt


def test_blast_radius_skill() -> None:
    p = SKILLS_DIR / "blast_radius.SKILL.md"
    assert p.exists()
    txt = p.read_text()
    assert "is_partial" in txt


def test_risk_classify_skill_exists() -> None:
    assert (SKILLS_DIR / "risk_classify.SKILL.md").exists()
