"""Hardened HTTP transport configuration."""

from __future__ import annotations

from collections.abc import Mapping
from os import environ

from pydantic import Field

from llm_sca_tooling.hardening.models import HTTPTransportConfig
from llm_sca_tooling.schemas.base import StrictBaseModel


class HTTPTransportReadiness(StrictBaseModel):
    ready: bool
    bind_url: str = Field(min_length=1)
    tls_enabled: bool
    auth_required: bool
    warnings: list[str] = Field(default_factory=list)


def build_http_transport_summary(config: HTTPTransportConfig) -> HTTPTransportReadiness:
    scheme = "https" if config.tls_enabled else "http"
    warnings: list[str] = []
    if config.single_user:
        warnings.append("single-user mode only")
    return HTTPTransportReadiness(
        ready=True,
        bind_url=f"{scheme}://{config.host}:{config.port}",
        tls_enabled=config.tls_enabled,
        auth_required=not config.single_user,
        warnings=warnings,
    )


def validate_http_transport_environment(
    config: HTTPTransportConfig,
    env: Mapping[str, str] | None = None,
) -> HTTPTransportReadiness:
    active_env = environ if env is None else env
    summary = build_http_transport_summary(config)
    warnings = list(summary.warnings)
    ready = summary.ready
    if config.auth_token_env_var and not active_env.get(config.auth_token_env_var):
        ready = False
        warnings.append("auth token environment variable is not set")
    if config.tls_enabled and not (config.tls_cert_path and config.tls_key_path):
        ready = False
        warnings.append(
            "TLS certificate and key paths are required when TLS is enabled"
        )
    return HTTPTransportReadiness(
        ready=ready,
        bind_url=summary.bind_url,
        tls_enabled=summary.tls_enabled,
        auth_required=summary.auth_required,
        warnings=warnings,
    )
