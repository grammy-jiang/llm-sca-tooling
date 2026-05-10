"""Unit tests for evidence-sca setup subcommand."""

from __future__ import annotations

import tomllib
from unittest.mock import patch

import orjson

from llm_sca_tooling.cli.setup_cmd import (
    SetupResult,
    _detect_claude_code,
    _detect_codex,
    _detect_copilot,
    print_results,
    run_setup,
)

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def test_detect_claude_code_via_binary(tmp_path):
    with patch("shutil.which", return_value="/usr/bin/claude"):
        assert _detect_claude_code() is True


def test_detect_claude_code_via_dir(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        assert _detect_claude_code() is True


def test_detect_claude_code_missing(tmp_path):
    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        assert _detect_claude_code() is False


def test_detect_codex_via_binary():
    with patch("shutil.which", return_value="/usr/bin/codex"):
        assert _detect_codex() is True


def test_detect_codex_missing(tmp_path):
    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        assert _detect_codex() is False


def test_detect_copilot_via_gh():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        assert _detect_copilot() is True


def test_detect_copilot_via_extension(tmp_path):
    ext_dir = tmp_path / ".vscode" / "extensions"
    ext_dir.mkdir(parents=True)
    (ext_dir / "github.copilot-1.0").mkdir()
    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        assert _detect_copilot() is True


# ---------------------------------------------------------------------------
# Claude Code configuration
# ---------------------------------------------------------------------------


def test_claude_code_writes_mcp_json(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    cc = next(r for r in results if r.agent == "claude-code")
    assert cc.configured is True
    assert cc.errors == []

    mcp_json = tmp_path / ".mcp.json"
    assert mcp_json.exists()
    data = orjson.loads(mcp_json.read_bytes())
    assert "evidence-sca" in data["mcpServers"]
    assert data["mcpServers"]["evidence-sca"]["command"] == "evidence-sca"
    assert data["mcpServers"]["evidence-sca"]["args"] == ["mcp", "serve"]


def test_claude_code_dry_run_does_not_write(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        run_setup(dry_run=True, repo_root=tmp_path)

    assert not (tmp_path / ".mcp.json").exists()


def test_claude_code_skips_if_already_configured(tmp_path):
    existing = {
        "mcpServers": {
            "evidence-sca": {"command": "evidence-sca", "args": ["mcp", "serve"]}
        }
    }
    (tmp_path / ".mcp.json").write_bytes(orjson.dumps(existing))
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    cc = next(r for r in results if r.agent == "claude-code")
    assert cc.skipped is True
    assert cc.configured is False


def test_claude_code_merges_existing_servers(tmp_path):
    existing = {"mcpServers": {"other-tool": {"command": "other", "args": []}}}
    (tmp_path / ".mcp.json").write_bytes(orjson.dumps(existing))
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        run_setup(repo_root=tmp_path)

    data = orjson.loads((tmp_path / ".mcp.json").read_bytes())
    assert "other-tool" in data["mcpServers"]
    assert "evidence-sca" in data["mcpServers"]


# ---------------------------------------------------------------------------
# GitHub Copilot configuration
# ---------------------------------------------------------------------------


def test_copilot_writes_vscode_mcp_json(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    cop = next(r for r in results if r.agent == "github-copilot")
    assert cop.configured is True

    mcp_json = tmp_path / ".vscode" / "mcp.json"
    assert mcp_json.exists()
    data = orjson.loads(mcp_json.read_bytes())
    assert "evidence-sca" in data["servers"]
    assert data["servers"]["evidence-sca"]["command"] == "evidence-sca"


def test_copilot_skips_if_already_configured(tmp_path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    existing = {"servers": {"evidence-sca": {"command": "evidence-sca", "args": []}}}
    (vscode / "mcp.json").write_bytes(orjson.dumps(existing))
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    cop = next(r for r in results if r.agent == "github-copilot")
    assert cop.skipped is True


# ---------------------------------------------------------------------------
# Codex CLI configuration
# ---------------------------------------------------------------------------


def test_codex_writes_config_toml(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=True),
    ):
        results = run_setup(repo_root=tmp_path)

    cod = next(r for r in results if r.agent == "codex-cli")
    assert cod.configured is True

    config_toml = tmp_path / ".codex" / "config.toml"
    assert config_toml.exists()
    data = tomllib.loads(config_toml.read_text(encoding="utf-8"))
    assert "evidence-sca" in data["mcp_servers"]
    assert data["mcp_servers"]["evidence-sca"]["command"] == "evidence-sca"


def test_codex_skips_if_already_configured(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        '[mcp_servers.evidence-sca]\ncommand = "evidence-sca"\n', encoding="utf-8"
    )
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=True),
    ):
        results = run_setup(repo_root=tmp_path)

    cod = next(r for r in results if r.agent == "codex-cli")
    assert cod.skipped is True


def test_codex_merges_existing_config(tmp_path):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        '[mcp_servers.other]\ncommand = "other"\n', encoding="utf-8"
    )
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=True),
    ):
        run_setup(repo_root=tmp_path)

    data = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert "other" in data["mcp_servers"]
    assert "evidence-sca" in data["mcp_servers"]


# ---------------------------------------------------------------------------
# All-skipped and skills-note paths
# ---------------------------------------------------------------------------


def test_all_skipped_when_no_agents(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    assert all(r.skipped for r in results)
    assert all(not r.configured for r in results)


def test_skills_note_included_when_skills_dir_exists(tmp_path):
    skills_dir = tmp_path / ".skills"
    skills_dir.mkdir()
    (skills_dir / "audit.SKILL.md").write_text("---\nname: audit\n---\n")
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        results = run_setup(repo_root=tmp_path)

    cc = next(r for r in results if r.agent == "claude-code")
    assert "audit" in cc.detail


def test_workspace_arg_propagated_to_mcp_args(tmp_path):
    with (
        patch("llm_sca_tooling.cli.setup_cmd._detect_claude_code", return_value=True),
        patch("llm_sca_tooling.cli.setup_cmd._detect_copilot", return_value=False),
        patch("llm_sca_tooling.cli.setup_cmd._detect_codex", return_value=False),
    ):
        run_setup(workspace="custom-ws", repo_root=tmp_path)

    data = orjson.loads((tmp_path / ".mcp.json").read_bytes())
    args = data["mcpServers"]["evidence-sca"]["args"]
    assert "--workspace" in args
    assert "custom-ws" in args


# ---------------------------------------------------------------------------
# print_results smoke test
# ---------------------------------------------------------------------------


def test_print_results_output(capsys):
    results = [
        SetupResult(agent="claude-code", configured=True, detail="wrote .mcp.json"),
        SetupResult(
            agent="codex-cli", configured=False, skipped=True, detail="not installed"
        ),
    ]
    print_results(results)
    out = capsys.readouterr().out
    assert "CONFIGURED" in out
    assert "SKIPPED" in out
