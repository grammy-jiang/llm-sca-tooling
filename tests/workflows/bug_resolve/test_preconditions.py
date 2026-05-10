"""Tests for the pre/postcondition draft generator."""

from __future__ import annotations

import pytest

from llm_sca_tooling.workflows.bug_resolve.preconditions import (
    generate_prepost_draft,
)


def test_basic_draft() -> None:
    d = generate_prepost_draft(
        run_id="r1",
        candidate_index=0,
        function_path="src/x.py:foo",
        preconditions=["x is not None"],
        postconditions=["return >= 0"],
    )
    assert d.preconditions == ["x is not None"]
    assert d.postconditions == ["return >= 0"]
    assert d.confidence == "unknown"


def test_compile_status_verified() -> None:
    d = generate_prepost_draft(
        run_id="r1",
        candidate_index=0,
        function_path="x:foo",
        compile_status="verified",
    )
    assert d.confidence == "verified"


def test_compile_status_compiles() -> None:
    d = generate_prepost_draft(
        run_id="r1",
        candidate_index=0,
        function_path="x:foo",
        compile_status="compiles",
    )
    assert d.confidence == "supporting"


def test_compile_status_unknown_default() -> None:
    d = generate_prepost_draft(
        run_id="r1",
        candidate_index=0,
        function_path="x:foo",
    )
    assert d.confidence == "unknown"


def test_empty_function_path_raises() -> None:
    with pytest.raises(ValueError):
        generate_prepost_draft(run_id="r1", candidate_index=0, function_path="")
