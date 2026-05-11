"""Tests for the Harness Condition Sheet writer."""

from __future__ import annotations

import pytest

from llm_sca_tooling.harness.condition import HarnessConditionWriter


@pytest.fixture()
def writer() -> HarnessConditionWriter:
    return HarnessConditionWriter()


def _make_hcs(writer: HarnessConditionWriter, **overrides: object) -> dict:
    defaults: dict[str, object] = {
        "run_id": "run:test123",
        "phase": "H0",
        "runtime_version": "claude-code/1.0",
        "model_backend": "claude-sonnet-4-6",
        "toolset_hash": "abc123",
        "permission_profile": "scoped-execute",
        "context_budget": 200_000,
        "gates_enabled": ["make verify"],
        "gates_disabled": [],
        "trace_location": ".agent/traces/s1.jsonl",
        "trace_completeness": "complete",
        "redaction_policy": "default",
    }
    defaults.update(overrides)
    return writer.capture(**defaults)  # type: ignore[arg-type]


def test_capture_returns_dict(writer: HarnessConditionWriter) -> None:
    hcs = _make_hcs(writer)
    assert isinstance(hcs, dict)


def test_capture_includes_run_id(writer: HarnessConditionWriter) -> None:
    hcs = _make_hcs(writer)
    assert hcs["run_id"] == "run:test123"


def test_capture_includes_all_required_fields(writer: HarnessConditionWriter) -> None:
    hcs = _make_hcs(writer)
    required = (
        "run_id",
        "report_date",
        "phase",
        "runtime_version",
        "model_backend",
        "toolset_hash",
        "permission_profile",
        "gates_enabled",
        "gates_disabled",
        "trace_completeness",
        "redaction_policy",
    )
    for field in required:
        assert field in hcs, f"Missing field: {field}"


def test_capture_with_no_context_budget(writer: HarnessConditionWriter) -> None:
    hcs = _make_hcs(writer, context_budget=None)
    assert hcs["context_budget"] is None


def test_capture_trace_completeness_stored(writer: HarnessConditionWriter) -> None:
    hcs = _make_hcs(writer, trace_completeness="incomplete")
    assert hcs["trace_completeness"] == "incomplete"
