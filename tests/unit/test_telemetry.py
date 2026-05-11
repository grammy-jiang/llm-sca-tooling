"""Tests for the telemetry logging helper."""

from __future__ import annotations

import logging

import pytest

from llm_sca_tooling.telemetry.logging import get_logger


def test_get_logger_returns_logger() -> None:
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"


def test_get_logger_idempotent() -> None:
    a = get_logger("test.idempotent")
    b = get_logger("test.idempotent")
    assert a is b


def test_get_logger_lazy_formatting(caplog: pytest.LogCaptureFixture) -> None:
    logger = get_logger("test.lazy")
    with caplog.at_level(logging.INFO, logger="test.lazy"):
        logger.info("Processing %d files in %s", 42, "/repo/example")
    assert "Processing 42 files in /repo/example" in caplog.text


def test_get_logger_respects_env_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SCA_LOG_LEVEL", "DEBUG")
    logger = get_logger("test.env.level")
    assert isinstance(logger, logging.Logger)
