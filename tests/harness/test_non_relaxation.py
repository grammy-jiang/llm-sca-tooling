"""Non-relaxation tests for AGENTS.md hard constraints HC1–HC6.

These tests verify that no manifest edit or runtime overlay has weakened any
of the six hard constraints. They run in CI and locally as part of the harness
regression suite.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


# ---------------------------------------------------------------------------
# Live tests — run now at every stage
# ---------------------------------------------------------------------------


def test_agents_md_exists() -> None:
    """AGENTS.md must exist at the repository root."""
    assert AGENTS_MD.exists(), "AGENTS.md is missing from the repository root"


def test_all_hard_constraints_present_in_agents_md() -> None:
    """AGENTS.md must declare all hard constraints HC1 through HC6."""
    content = AGENTS_MD.read_text()
    for hc_id in ("HC1", "HC2", "HC3", "HC4", "HC5", "HC6"):
        assert (
            hc_id in content
        ), f"{hc_id} is missing from AGENTS.md — hard constraint removed"


def test_non_relaxation_declaration_present() -> None:
    """AGENTS.md must contain the non-relaxation declaration."""
    content = AGENTS_MD.read_text()
    assert (
        "never be relaxed" in content.lower() or "non-relaxation" in content.lower()
    ), "Non-relaxation declaration is missing from AGENTS.md"


def test_runtime_overlays_present() -> None:
    """At least one runtime overlay must exist and declare AGENTS.md precedence."""
    overlays = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / ".github" / "copilot-instructions.md",
        REPO_ROOT / ".codex" / "INSTRUCTIONS.md",
    ]
    existing = [p for p in overlays if p.exists()]
    assert existing, "No runtime overlay files found — at least one is required"

    for overlay in existing:
        content = overlay.read_text()
        declares_precedence = "@AGENTS.md" in content or "AGENTS.md" in content
        assert declares_precedence, (
            f"{overlay.relative_to(REPO_ROOT)} does not reference AGENTS.md — "
            "overlay must declare AGENTS.md precedence"
        )


def test_secrets_baseline_exists() -> None:
    """A detect-secrets baseline must exist (HC1 enforcement)."""
    baseline = REPO_ROOT / ".secrets.baseline"
    assert (
        baseline.exists()
    ), ".secrets.baseline is missing — run: uv run detect-secrets scan > .secrets.baseline"


def test_makefile_detect_secrets_does_not_scan_baseline_file() -> None:
    """The secrets gate must not treat the baseline file as a new secret source."""
    makefile = REPO_ROOT / "Makefile"
    content = makefile.read_text()
    assert "--exclude-files" in content
    assert r"\.secrets\.baseline" in content


def test_pre_commit_config_has_secrets_scan() -> None:
    """Pre-commit config must include a secrets-detection hook."""
    config = REPO_ROOT / ".pre-commit-config.yaml"
    assert config.exists(), ".pre-commit-config.yaml is missing"
    content = config.read_text()
    has_detect_secrets = "detect-secrets" in content
    has_gitleaks = "gitleaks" in content
    assert (
        has_detect_secrets or has_gitleaks
    ), ".pre-commit-config.yaml has no secrets-scan hook — HC1 pre-commit enforcement missing"


# ---------------------------------------------------------------------------
# S1+ stub tests — implement in Phase 4 when overlay parser is available
# ---------------------------------------------------------------------------


def test_claude_md_does_not_relax_hc1() -> None:
    """CLAUDE.md must not weaken HC1 (no plaintext secrets)."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        pytest.skip("CLAUDE.md not present")
    content = claude_md.read_text()
    forbidden = [
        "disable detect-secrets",
        "skip secret scan",
        "allow secrets",
        "ignore_missing_secrets",
        "skip_hc",
        "disable_hc",
    ]
    for pattern in forbidden:
        assert (
            pattern not in content.lower()
        ), f"CLAUDE.md contains HC1-relaxing language: {pattern!r}"


def test_copilot_instructions_does_not_relax_hc5() -> None:
    """copilot-instructions.md must not add network destinations outside the AGENTS.md allowlist."""
    copilot_inst = REPO_ROOT / ".github" / "copilot-instructions.md"
    if not copilot_inst.exists():
        pytest.skip("copilot-instructions.md not present")
    content = copilot_inst.read_text()
    forbidden = [
        "allow_all",
        "network_unrestricted",
        "disable network deny",
        "allow all network",
    ]
    for pattern in forbidden:
        assert (
            pattern not in content.lower()
        ), f"copilot-instructions.md contains HC5-relaxing language: {pattern!r}"


def test_codex_instructions_does_not_relax_hc3() -> None:
    """INSTRUCTIONS.md must not remove the approval requirement for destructive commands."""
    codex_inst = REPO_ROOT / ".codex" / "INSTRUCTIONS.md"
    if not codex_inst.exists():
        pytest.skip(".codex/INSTRUCTIONS.md not present")
    content = codex_inst.read_text()
    forbidden = [
        "force push allowed",
        "skip approval",
        "no human needed",
        "disable_hc",
        "skip_hc",
    ]
    for pattern in forbidden:
        assert (
            pattern not in content.lower()
        ), f".codex/INSTRUCTIONS.md contains HC3-relaxing language: {pattern!r}"


def test_no_pre_commit_hook_disabled_without_waiver() -> None:
    """No verify gate may be silently disabled in .pre-commit-config.yaml."""
    config = REPO_ROOT / ".pre-commit-config.yaml"
    assert config.exists(), ".pre-commit-config.yaml is missing"
    content = config.read_text()

    # Check that no hook is fully skipped by setting stages: []
    assert "stages: []" not in content, (
        ".pre-commit-config.yaml contains 'stages: []' which disables a hook "
        "— this requires a reviewed waiver"
    )
    # No relaxation patterns
    for pattern in ("ignore_missing_secrets", "skip_hc", "disable_hc", "allow_all"):
        assert (
            pattern not in content
        ), f".pre-commit-config.yaml contains relaxation pattern: {pattern!r}"
