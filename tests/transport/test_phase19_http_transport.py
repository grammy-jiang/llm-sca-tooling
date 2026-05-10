from __future__ import annotations

import pytest

from llm_sca_tooling.hardening.models import HTTPTransportConfig
from llm_sca_tooling.transport.http_transport import (
    build_http_transport_summary,
    validate_http_transport_environment,
)


def test_http_transport_rejects_wildcard_cors() -> None:
    with pytest.raises(ValueError, match="wildcard CORS"):
        HTTPTransportConfig(cors_allowed_origins=["*"])


def test_http_transport_requires_tls_for_nonlocal_hosts() -> None:
    with pytest.raises(ValueError, match="TLS is required"):
        HTTPTransportConfig(host="192.0.2.1")


def test_http_transport_requires_auth_env_for_multi_user() -> None:
    config = HTTPTransportConfig(
        single_user=False,
        auth_token_env_var="EVIDENCE_SCA_HTTP_TOKEN",
    )
    readiness = validate_http_transport_environment(config, env={})
    assert not readiness.ready
    assert readiness.auth_required


def test_http_transport_summary_reports_local_url() -> None:
    summary = build_http_transport_summary(HTTPTransportConfig(port=9090))
    assert summary.bind_url == "http://127.0.0.1:9090"
