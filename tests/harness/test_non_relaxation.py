from __future__ import annotations

from pathlib import Path


def test_agents_keeps_all_hard_constraints() -> None:
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    for constraint in ["HC1", "HC2", "HC3", "HC4", "HC5", "HC6"]:
        assert constraint in text


def test_runtime_overlays_do_not_claim_precedence_over_agents() -> None:
    overlays = [
        Path("CLAUDE.md"),
        Path(".codex/INSTRUCTIONS.md"),
        Path(".github/copilot-instructions.md"),
    ]
    forbidden = [
        "override AGENTS.md",
        "ignore AGENTS.md",
        "disable HC",
        "bypass AGENTS.md",
    ]
    for path in overlays:
        text = path.read_text(encoding="utf-8")
        assert not any(pattern in text for pattern in forbidden)
