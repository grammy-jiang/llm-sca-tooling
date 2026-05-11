"""Tests for the configuration model and loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_sca_tooling.config import Config, TelemetryConfig, load_config
from llm_sca_tooling.errors import ConfigError


def test_default_config_is_valid() -> None:
    cfg = Config()
    assert cfg.package_name == "llm-sca-tooling"
    assert cfg.version == "0.1.0"
    assert cfg.policy.permission_profile == "read-only"
    assert cfg.policy.network_deny_by_default is True


def test_config_invalid_permission_profile() -> None:
    with pytest.raises((ValueError, Exception)):
        Config(policy={"permission_profile": "superuser"})  # type: ignore[arg-type]


def test_load_config_no_file() -> None:
    cfg = load_config()
    assert isinstance(cfg, Config)


def test_load_config_json_file(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"version": "9.9.9"}))
    cfg = load_config(cfg_file)
    assert cfg.version == "9.9.9"


def test_load_config_toml_file(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('version = "8.8.8"\n')
    cfg = load_config(cfg_file)
    assert cfg.version == "8.8.8"


def test_load_config_unsupported_format(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("version: 1.0")
    with pytest.raises(ConfigError, match="Unsupported"):
        load_config(cfg_file)


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(tmp_path / "nonexistent.toml")


def test_config_redacted_hides_sensitive_keys() -> None:
    cfg = Config()
    redacted = cfg.redacted()
    for key in redacted:
        if any(s in key.lower() for s in {"token", "secret", "password", "api_key"}):
            assert redacted[key] == "***REDACTED***"


def test_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SCA_VERSION", "env-version")
    cfg = Config()
    assert cfg.version == "env-version"


def test_telemetry_config_defaults() -> None:
    t = TelemetryConfig()
    assert t.enabled is True
    assert t.trace_dir == Path(".agent/traces")
