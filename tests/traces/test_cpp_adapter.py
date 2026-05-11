"""Tests for CppTraceAdapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_sca_tooling.traces.adapters.cpp_adapter import (
    CppTraceAdapter,
    CppTraceAdapterPlaceholder,
)
from llm_sca_tooling.traces.models import (
    ScopeFilter,
    TraceLanguage,
    TraceRunContract,
    TraceRunStatus,
)


def _make_contract(tmp_path: Path) -> TraceRunContract:
    return TraceRunContract(
        contract_id="contract:test-cpp",
        command="./app",
        args=[],
        timeout_seconds=30,
        working_dir=str(tmp_path),
        scope_filter=ScopeFilter(include_modules=["mymodule"]),
        language=TraceLanguage.CPP,
        adapter_id="cpp-probe/v1",
    )


def _make_mock_proc(
    returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
) -> MagicMock:
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.kill = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return mock_proc


def test_cpp_adapter_class_attributes() -> None:
    adapter = CppTraceAdapter()
    assert adapter.adapter_id == "cpp-probe/v1"
    assert adapter.adapter_version == "cpp-probe/v1"
    assert "c" in adapter.supported_languages
    assert "cpp" in adapter.supported_languages


def test_cpp_adapter_placeholder_is_alias() -> None:
    assert CppTraceAdapterPlaceholder is CppTraceAdapter


@pytest.mark.asyncio
async def test_cpp_adapter_not_implemented_when_no_tools(tmp_path: Path) -> None:
    with patch("shutil.which", return_value=None):
        adapter = CppTraceAdapter()
        contract = _make_contract(tmp_path)
        result = await adapter.capture(
            trace_run_id="trace:cpp-test",
            contract=contract,
            artifact_root=tmp_path / "artifacts",
        )
    assert result.status is TraceRunStatus.NOT_IMPLEMENTED
    assert any(
        d.get("code") == "cpp_trace_adapter_not_available" for d in result.diagnostics
    )


@pytest.mark.asyncio
async def test_cpp_adapter_completes_when_rr_available(tmp_path: Path) -> None:
    def which_side_effect(name: str) -> str | None:
        return "/usr/bin/rr" if name == "rr" else None

    mock_proc = _make_mock_proc()

    async def fake_subprocess(*args: object, **kwargs: object) -> MagicMock:
        return mock_proc

    with (
        patch("shutil.which", side_effect=which_side_effect),
        patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess),
    ):
        adapter = CppTraceAdapter()
        contract = _make_contract(tmp_path)
        result = await adapter.capture(
            trace_run_id="trace:cpp-test",
            contract=contract,
            artifact_root=tmp_path / "artifacts",
        )
    assert result.status is TraceRunStatus.COMPLETED
    assert result.raw_artefact is not None
    assert result.raw_artefact.adapter_version == "cpp-probe/v1"
    assert result.raw_artefact.event_count == 0
    assert Path(result.raw_artefact.events_jsonl_path).exists()


@pytest.mark.asyncio
async def test_cpp_adapter_completes_when_gdb_available(tmp_path: Path) -> None:
    def which_side_effect(name: str) -> str | None:
        return "/usr/bin/gdb" if name == "gdb" else None

    mock_proc = _make_mock_proc()

    async def fake_subprocess(*args: object, **kwargs: object) -> MagicMock:
        return mock_proc

    with (
        patch("shutil.which", side_effect=which_side_effect),
        patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess),
    ):
        adapter = CppTraceAdapter()
        contract = _make_contract(tmp_path)
        result = await adapter.capture(
            trace_run_id="trace:cpp-test",
            contract=contract,
            artifact_root=tmp_path / "artifacts",
        )
    assert result.status is TraceRunStatus.COMPLETED
    assert result.raw_artefact is not None
