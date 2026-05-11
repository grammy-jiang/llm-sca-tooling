"""Streamable HTTP transport configuration and startup.

Phase 19 adds Streamable HTTP transport alongside the existing stdio
transport.  The same ``FastMCP`` server handles both; transport is
selected at startup.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["HTTPTransportConfig", "start_http_server"]

logger = get_logger(__name__)

_WILDCARD_ORIGIN = "*"


class HTTPTransportConfig(BaseModel):
    """Configuration for the Streamable HTTP MCP transport.

    TLS is required for non-localhost deployments.
    Auth token is required when ``single_user`` is ``False``.
    CORS wildcard origin is rejected.
    """

    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = 8080
    tls_enabled: bool = False
    tls_cert_path: str | None = None
    tls_key_path: str | None = None
    cors_allowed_origins: list[str] = []
    auth_token_env_var: str | None = None
    rate_limit_requests_per_minute: int = 60
    max_connections: int = 100
    single_user: bool = True
    transport: Literal["stdio", "http"] = "http"

    @field_validator("cors_allowed_origins")
    @classmethod
    def reject_wildcard(cls, v: list[str]) -> list[str]:
        if _WILDCARD_ORIGIN in v:
            raise ValueError(
                "CORS wildcard origin '*' is not permitted. "
                "Specify explicit allowed origins."
            )
        return v

    def validate_security(self) -> list[str]:
        """Return a list of security policy violations (empty = OK)."""
        violations: list[str] = []
        if not self.single_user and self.auth_token_env_var is None:
            violations.append("auth_token_env_var is required when single_user=False")
        is_localhost = self.host in ("127.0.0.1", "::1", "localhost")
        if not is_localhost and not self.tls_enabled:
            violations.append("tls_enabled must be True for non-localhost deployments")
        if self.tls_enabled and (
            self.tls_cert_path is None or self.tls_key_path is None
        ):
            violations.append(
                "tls_cert_path and tls_key_path must be set when tls_enabled=True"
            )
        return violations


def start_http_server(
    config: HTTPTransportConfig,
    mcp_app: object,
) -> None:  # pragma: no cover — integration entry point
    """Start the FastMCP server using uvicorn in HTTP mode.

    Validates security policy before starting; aborts on violations.

    Args:
        config: HTTP transport configuration.
        mcp_app: The ``FastMCP`` application instance.
    """
    violations = config.validate_security()
    if violations:
        for v in violations:
            logger.error("HTTP transport security violation: %s", v)
        raise ValueError(f"HTTP transport security violations: {violations}")

    logger.info(
        "Starting HTTP MCP server on %s:%d (tls=%s)",
        config.host,
        config.port,
        config.tls_enabled,
    )

    try:
        import uvicorn  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("uvicorn is required for HTTP transport") from exc

    # Resolve the ASGI app from whatever was passed.
    # MCPServer wraps FastMCP in ._mcp; FastMCP exposes .http_app().
    _resolved = getattr(mcp_app, "_mcp", mcp_app)
    _http_app_factory = getattr(_resolved, "http_app", None)
    asgi_app: object
    if callable(_http_app_factory):
        asgi_app = _http_app_factory()
    else:
        asgi_app = getattr(_resolved, "app", _resolved)

    ssl_kwargs: dict[str, object] = {}
    if config.tls_enabled and config.tls_cert_path and config.tls_key_path:
        ssl_kwargs = {
            "ssl_certfile": config.tls_cert_path,
            "ssl_keyfile": config.tls_key_path,
        }

    uvicorn.run(
        asgi_app,  # type: ignore[arg-type]
        host=config.host,
        port=config.port,
        **ssl_kwargs,  # type: ignore[arg-type]
    )
