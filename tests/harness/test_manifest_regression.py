from __future__ import annotations

from pathlib import Path


def test_required_manifests_exist() -> None:
    for path in [
        "AGENTS.md",
        "CLAUDE.md",
        ".codex/INSTRUCTIONS.md",
        ".github/copilot-instructions.md",
    ]:
        assert Path(path).exists()


def test_verify_command_is_documented() -> None:
    assert "make verify" in Path("AGENTS.md").read_text(encoding="utf-8")
