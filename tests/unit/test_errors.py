"""Tests for the structured error hierarchy."""

import pytest

from llm_sca_tooling.errors import (
    BudgetExhaustedError,
    ClosedRunError,
    ConfigError,
    LLMSCAError,
    NotImplementedFeatureError,
    PluginError,
    PolicyViolationError,
    SchemaValidationError,
)


def test_all_errors_are_llmsca_subclasses() -> None:
    for cls in (
        ConfigError,
        PolicyViolationError,
        BudgetExhaustedError,
        PluginError,
        SchemaValidationError,
        ClosedRunError,
        NotImplementedFeatureError,
    ):
        assert issubclass(cls, LLMSCAError)


def test_errors_are_catchable_as_base() -> None:
    for cls in (ConfigError, PolicyViolationError, ClosedRunError):
        with pytest.raises(LLMSCAError):
            raise cls("test message")


def test_not_implemented_feature_error_message() -> None:
    exc = NotImplementedFeatureError("embeddings not yet available")
    assert "embeddings" in str(exc)


def test_closed_run_error_is_distinct_from_base_llmsca() -> None:
    exc = ClosedRunError("run:abc closed")
    assert isinstance(exc, LLMSCAError)
    assert not isinstance(exc, ConfigError)


def test_errors_chain_correctly() -> None:
    original = ValueError("root cause")
    wrapped = ConfigError("config failed")
    try:
        raise wrapped from original
    except ConfigError as exc:
        assert exc.__cause__ is original
