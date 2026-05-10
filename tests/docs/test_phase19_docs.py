from __future__ import annotations

from pathlib import Path


def test_phase19_operator_docs_exist() -> None:
    docs = [
        "installation.md",
        "quickstart.md",
        "architecture.md",
        "plugin-authoring-guide.md",
        "evaluation-guide.md",
        "harness-setup-guide.md",
        "incident-response-guide.md",
    ]
    for name in docs:
        text = (Path("docs") / name).read_text(encoding="utf-8")
        assert "## Limitations" in text
        assert "HarnessConditionSheet" in text


def test_devcontainer_template_is_documented_not_materialized() -> None:
    text = Path("docs/devcontainer-template.md").read_text(encoding="utf-8")
    assert "does not allow writing `.devcontainer/` directly" in text
