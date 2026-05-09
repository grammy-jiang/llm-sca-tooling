"""Typed package configuration and loading helpers."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from llm_sca_tooling import __version__
from llm_sca_tooling.errors import ConfigError

SENSITIVE_KEY_PARTS = ("api_key", "apikey", "credential", "password", "secret", "token")
NON_SECRET_TOKEN_KEYS = {
    "context_budget",
    "max_tokens",
    "token_budget",
    "token_count",
    "tokens_limit",
    "tokens_used",
}


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_dir: Path = Path(".agent/traces")
    enabled: bool = True


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tokens: int = 100_000
    max_tool_calls: int = 200
    max_retries: int = 3
    max_wall_seconds: int = 3600

    @field_validator("max_tokens", "max_tool_calls", "max_retries", "max_wall_seconds")
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("budget limits must be positive")
        return value


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission_profile: str = "read-only"
    path_allowlist: list[str] = Field(default_factory=list)
    network_deny_by_default: bool = True


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = 8765
    dev_mode: bool = True

    @field_validator("port")
    @classmethod
    def _valid_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("port must be between 1 and 65535")
        return value


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    package_name: str = "llm-sca-tooling"
    version: str = __version__
    workspace_root: Path = Path(".")
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)


def load_config(path: Path | str | None = None) -> Config:
    """Load defaults, an optional JSON/TOML config file, then env overrides."""

    payload: dict[str, Any] = {}
    config_path = Path(path) if path is not None else _default_config_path()
    if config_path is not None and config_path.exists():
        payload = _load_config_file(config_path)
    payload = _deep_merge(payload, _env_overrides())
    try:
        return Config.model_validate(payload)
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc


def redacted_config(config: Config) -> dict[str, Any]:
    """Return a JSON-compatible config dict with sensitive keys redacted."""

    return redact_sensitive_fields(config.model_dump(mode="json"))


def redact_sensitive_fields(value: Any) -> Any:
    """Recursively redact known-sensitive key names."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_sensitive_fields(child)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    return value


def _default_config_path() -> Path | None:
    for candidate in (Path("llm-sca.toml"), Path("llm-sca.json")):
        if candidate.exists():
            return candidate
    return None


def _load_config_file(path: Path) -> dict[str, Any]:
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if path.suffix in {".toml", ".tml"}:
            return tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"could not read config file {path}: {exc}") from exc
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not parse config file {path}: {exc}") from exc
    raise ConfigError(f"unsupported config file extension: {path.suffix}")


def _env_overrides() -> dict[str, Any]:
    mapping: dict[str, tuple[str, ...]] = {
        "LLM_SCA_WORKSPACE_ROOT": ("workspace_root",),
        "LLM_SCA_TELEMETRY_ENABLED": ("telemetry", "enabled"),
        "LLM_SCA_TELEMETRY_TRACE_DIR": ("telemetry", "trace_dir"),
        "LLM_SCA_BUDGET_MAX_TOKENS": ("budget", "max_tokens"),
        "LLM_SCA_BUDGET_MAX_TOOL_CALLS": ("budget", "max_tool_calls"),
        "LLM_SCA_BUDGET_MAX_RETRIES": ("budget", "max_retries"),
        "LLM_SCA_BUDGET_MAX_WALL_SECONDS": ("budget", "max_wall_seconds"),
        "LLM_SCA_POLICY_PERMISSION_PROFILE": ("policy", "permission_profile"),
        "LLM_SCA_POLICY_NETWORK_DENY_BY_DEFAULT": ("policy", "network_deny_by_default"),
        "LLM_SCA_MCP_HOST": ("mcp", "host"),
        "LLM_SCA_MCP_PORT": ("mcp", "port"),
        "LLM_SCA_MCP_DEV_MODE": ("mcp", "dev_mode"),
    }
    payload: dict[str, Any] = {}
    for env_name, path in mapping.items():
        if env_name not in os.environ:
            continue
        _assign_nested(payload, path, _coerce_env_value(os.environ[env_name]))
    if "LLM_SCA_POLICY_PATH_ALLOWLIST" in os.environ:
        _assign_nested(
            payload,
            ("policy", "path_allowlist"),
            [
                part
                for part in os.environ["LLM_SCA_POLICY_PATH_ALLOWLIST"].split(
                    os.pathsep
                )
                if part
            ],
        )
    return payload


def _assign_nested(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = payload
    for key in path[:-1]:
        child = cursor.setdefault(key, {})
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


def _coerce_env_value(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    if lowered.isdigit():
        return int(lowered)
    return value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in NON_SECRET_TOKEN_KEYS:
        return False
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
