"""Configuration model for llm-sca-tooling.

Layer order (lowest to highest priority):
  1. Pydantic field defaults
  2. Config file (TOML or JSON), if provided
  3. Environment variables with the ``LLM_SCA_`` prefix
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_sca_tooling.errors import ConfigError

__all__ = [
    "TelemetryConfig",
    "BudgetConfig",
    "PolicyConfig",
    "MCPConfig",
    "Config",
    "load_config",
]

_SENSITIVE_SEGMENTS = frozenset(
    {"key", "token", "secret", "password", "credential", "auth"}
)


def _is_sensitive_key(name: str) -> bool:
    """Return True if any underscore-separated segment of *name* is a sensitive term."""
    parts = name.lower().replace("-", "_").split("_")
    return any(p in _SENSITIVE_SEGMENTS for p in parts)


class TelemetryConfig(BaseModel):
    trace_dir: Path = Path(".agent/traces")
    enabled: bool = True


class BudgetConfig(BaseModel):
    max_tokens: int = 100_000
    max_tool_calls: int = 200
    max_retries: int = 3
    max_wall_seconds: int = 3600


class PolicyConfig(BaseModel):
    permission_profile: str = "read-only"
    path_allowlist: list[str] = []
    network_deny_by_default: bool = True

    @field_validator("permission_profile")
    @classmethod
    def _valid_profile(cls, v: str) -> str:
        valid = {"read-only", "plan", "scoped-edit", "scoped-execute", "review-commit"}
        if v not in valid:
            msg = f"permission_profile must be one of {sorted(valid)}, got {v!r}"
            raise ValueError(msg)
        return v


class MCPConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3000
    dev_mode: bool = True


class Config(BaseSettings):
    """Top-level configuration loaded from file and environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_SCA_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    package_name: str = "llm-sca-tooling"
    version: str = "0.1.0"
    workspace_root: Path = Path()
    telemetry: TelemetryConfig = TelemetryConfig()
    budget: BudgetConfig = BudgetConfig()
    policy: PolicyConfig = PolicyConfig()
    mcp: MCPConfig = MCPConfig()

    def redacted(self) -> dict[str, Any]:
        """Return a copy of the config with sensitive values replaced."""
        data = self.model_dump()
        return _redact_dict(data)


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        if _is_sensitive_key(k):
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = _redact_dict(v)
        else:
            result[k] = v
    return result


def load_config(path: Path | None = None) -> Config:
    """Load configuration from an optional file, then overlay env vars.

    Args:
        path: Path to a TOML or JSON configuration file, or None to use
              only defaults and environment variables.

    Returns:
        A validated Config instance.

    Raises:
        ConfigError: If the file format is unsupported or validation fails.
    """
    file_data: dict[str, Any] = {}

    if path is not None:
        suffix = path.suffix.lower()
        try:
            if suffix == ".toml":
                with path.open("rb") as f:
                    file_data = tomllib.load(f)
            elif suffix == ".json":
                import json

                with path.open() as f:
                    file_data = json.load(f)
            else:
                raise ConfigError(f"Unsupported config file format: {suffix!r}")
        except OSError as exc:
            raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    try:
        return Config(**file_data)
    except (ValidationError, ValueError) as exc:
        raise ConfigError(f"Configuration validation failed: {exc}") from exc
