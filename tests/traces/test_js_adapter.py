"""Tests for JSTraceAdapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from llm_sca_tooling.traces.adapters.js_adapter import (
    JSTraceAdapter,
    JSTraceAdapterPlaceholder,
)
from llm_sca_tooling.traces.models import (
    ScopeFilter,
    TraceLanguage,
    TraceRunContract,
    TraceRunStatus,
)


def _make_contract(tmp_path: Path) -> TraceRunContract:
    return TraceRunContract(
        contract_id="contract:test-js",
        command="node",
        args=["app.js"],
        timeout_seconds=30,
        working_dir=str(tmp_path),
        scope_filter=ScopeFilter(include_modules=["mymodule"]),
        language=TraceLanguage.JAVASCRIPT,
        adapter_id="node-inspector/v1",
    )


def test_js_adapter_class_attributes() -> None:
    adapter = JSTraceAdapter()
    assert adapter.adapter_id == "node-inspector/v1"
    assert adapter.adapter_version == "node-inspector/v1"
    assert "javascript" in adapter.supported_languages
    assert "typescript" in adapter.supported_languages


def test_js_adapter_placeholder_is_alias() -> None:
    assert JSTraceAdapterPlaceholder is JSTraceAdapter


@pytest.mark.asyncio
async def test_js_adapter_not_implemented_when_no_node(tmp_path: Path) -> None:
    with patch("shutil.which", return_value=None):
        adapter = JSTraceAdapter()
        contract = _make_contract(tmp_path)
        result = await adapter.capture(
            trace_run_id="trace:test",
            contract=contract,
            artifact_root=tmp_path / "artifacts",
        )
    assert result.status is TraceRunStatus.NOT_IMPLEMENTED
    assert any(
        d.get("code") == "js_trace_adapter_not_available" for d in result.diagnostics
    )


@pytest.mark.asyncio
async def test_js_adapter_completes_when_node_available(tmp_path: Path) -> None:
    with patch("shutil.which", return_value="/usr/bin/node"):
        adapter = JSTraceAdapter()
        contract = _make_contract(tmp_path)
        result = await adapter.capture(
            trace_run_id="trace:test",
            contract=contract,
            artifact_root=tmp_path / "artifacts",
        )
    assert result.status is TraceRunStatus.COMPLETED
    assert result.raw_artefact is not None
    assert result.raw_artefact.adapter_version == "node-inspector/v1"
    assert result.raw_artefact.event_count == 0
    assert Path(result.raw_artefact.events_jsonl_path).exists()
