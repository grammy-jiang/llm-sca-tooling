"""Shared fixtures for patch-review tests."""

from __future__ import annotations

from pathlib import Path

import pytest

DIFF_DIR = Path(__file__).parent / "fixtures" / "diffs"


def _read(name: str) -> str:
    return (DIFF_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def safe_diff() -> str:
    return _read("safe_fix.diff")


@pytest.fixture
def vulnerable_diff() -> str:
    return _read("vulnerable_fix.diff")


@pytest.fixture
def overfit_diff() -> str:
    return _read("overfit_fix.diff")


@pytest.fixture
def scope_violation_diff() -> str:
    return _read("scope_violation.diff")


@pytest.fixture
def missing_test_diff() -> str:
    return _read("missing_test_fix.diff")
