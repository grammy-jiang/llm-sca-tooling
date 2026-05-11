"""Tests for HTTPTransportConfig."""

from __future__ import annotations

import pytest

from llm_sca_tooling.transport.http_transport import HTTPTransportConfig


def test_valid_config_accepted() -> None:
    cfg = HTTPTransportConfig(
        host="127.0.0.1",
        port=8080,
    )
    assert cfg.port == 8080


def test_wildcard_cors_rejected() -> None:
    with pytest.raises(ValueError, match="[Ww]ildcard|\\*"):
        HTTPTransportConfig(
            host="0.0.0.0",  # noqa: S104
            port=8080,
            cors_allowed_origins=["*"],
        )


def test_validate_security_flags_open_host_without_tls() -> None:
    cfg = HTTPTransportConfig(
        host="0.0.0.0",  # noqa: S104
        port=8080,
    )
    violations = cfg.validate_security()
    assert len(violations) >= 1


def test_localhost_no_security_violations() -> None:
    cfg = HTTPTransportConfig(
        host="127.0.0.1",
        port=8080,
    )
    violations = cfg.validate_security()
    assert len(violations) == 0


def test_multi_user_without_auth_token_is_violation() -> None:
    cfg = HTTPTransportConfig(
        host="127.0.0.1",
        port=8080,
        single_user=False,
        auth_token_env_var=None,
    )
    violations = cfg.validate_security()
    assert any("auth_token" in v for v in violations)
