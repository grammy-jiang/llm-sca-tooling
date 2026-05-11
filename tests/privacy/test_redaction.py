"""Tests for PrivacyRedactionPipeline."""

from __future__ import annotations

import pytest

from llm_sca_tooling.privacy.redaction import PrivacyRedactionPipeline
from llm_sca_tooling.privacy.retention_policy import RetentionPolicy


def _policy(**kwargs) -> RetentionPolicy:
    return RetentionPolicy(workspace_id="ws1", **kwargs)


def test_no_secrets_passes() -> None:
    pipeline = PrivacyRedactionPipeline(policy=_policy())
    result = pipeline.process({"event": "start", "data": "hello world"})
    assert "[REDACTED]" not in str(result)


def test_aws_key_style_secret_rejected_at_write_time() -> None:
    pipeline = PrivacyRedactionPipeline(policy=_policy())
    # Value matching "api_key = ..." pattern triggers rejection
    with pytest.raises(ValueError, match="[Ss]ecret|field"):
        pipeline.reject_if_secret({"data": "api_key = AKIAIOSFODNN7EXAMPLE1234"})


def test_reject_passes_for_clean_record() -> None:
    pipeline = PrivacyRedactionPipeline(policy=_policy())
    pipeline.reject_if_secret({"event": "start", "data": "hello"})  # must not raise


def test_nested_dict_processed_without_error() -> None:
    pipeline = PrivacyRedactionPipeline(policy=_policy())
    result = pipeline.process({"outer": {"inner": "safe text"}})
    assert result["outer"]["inner"] == "safe text"


def test_secret_scan_disabled_skips_scan() -> None:
    pipeline = PrivacyRedactionPipeline(policy=_policy(secret_scan_enabled=False))
    # Should not raise even if value looks like a secret
    pipeline.reject_if_secret({"api_key": "AKIAIOSFODNN7EXAMPLE"})
