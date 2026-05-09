from __future__ import annotations

import json

import pytest

from llm_sca_tooling.config import Config, load_config, redacted_config
from llm_sca_tooling.errors import ConfigError


def test_default_config_loads() -> None:
    config = load_config()
    assert config.package_name == "llm-sca-tooling"
    assert config.policy.permission_profile == "read-only"


def test_config_loads_json_and_env_override(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"mcp": {"port": 9000}, "budget": {"max_tokens": 50}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_SCA_MCP_PORT", "9100")
    loaded = load_config(config_path)
    assert loaded.mcp.port == 9100
    assert loaded.budget.max_tokens == 50


def test_config_rejects_invalid_file(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_redacted_config_hides_sensitive_keys() -> None:
    data = redacted_config(Config())
    assert redacted_config(Config())["package_name"] == "llm-sca-tooling"
    assert data["budget"]["max_tokens"] == 100_000


def test_redact_sensitive_fields_hides_secret_tokens() -> None:
    from llm_sca_tooling.config import redact_sensitive_fields

    assert redact_sensitive_fields({"token": "secret"})["token"] == "[REDACTED]"
