"""Shared fixtures for the sast-repair test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
ALERTS_DIR = FIXTURE_DIR / "alerts"
CORPUS_DIR = FIXTURE_DIR / "corpus"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def corpus_root() -> Path:
    return CORPUS_DIR


@pytest.fixture
def nullderef_alert() -> dict:
    return _read_json(ALERTS_DIR / "nullderef_alert.json")


@pytest.fixture
def injection_alert() -> dict:
    return _read_json(ALERTS_DIR / "injection_alert.json")


@pytest.fixture
def false_positive_alert() -> dict:
    return _read_json(ALERTS_DIR / "false_positive_alert.json")


@pytest.fixture
def unknown_alert() -> dict:
    return _read_json(ALERTS_DIR / "unknown_alert.json")
