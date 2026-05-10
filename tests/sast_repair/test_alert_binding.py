"""Tests for alert binding."""

from __future__ import annotations

import pytest

from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.models import BindingConfidence


def test_bind_alert_parser_confidence(nullderef_alert: dict) -> None:
    binding = bind_alert(
        alert=nullderef_alert,
        graph_snapshot_id="g1",
        sarif_snapshot_id="g1",
        file_node_lookup={"src/example.py": "node:file:src/example.py"},
        symbol_lookup={("src/example.py", 10): ["node:sym:foo"]},
    )
    assert binding.confidence is BindingConfidence.PARSER
    assert binding.file_node_id == "node:file:src/example.py"
    assert binding.primary_symbol_node_ids == ["node:sym:foo"]
    assert binding.diagnostics == []


def test_bind_alert_analyser_no_symbols(nullderef_alert: dict) -> None:
    binding = bind_alert(
        alert=nullderef_alert,
        file_node_lookup={"src/example.py": "node:file:1"},
    )
    assert binding.confidence is BindingConfidence.ANALYSER


def test_bind_alert_heuristic_no_file_node(nullderef_alert: dict) -> None:
    binding = bind_alert(alert=nullderef_alert)
    assert binding.confidence is BindingConfidence.HEURISTIC


def test_bind_alert_no_location_diagnostic() -> None:
    binding = bind_alert(alert={"alert_id": "a"})
    assert binding.confidence is BindingConfidence.NONE
    assert any(d["code"] == "no_location" for d in binding.diagnostics)


def test_bind_alert_no_file_path_diagnostic() -> None:
    binding = bind_alert(alert={"alert_id": "a", "locations": [{"file_path": "x.py"}]})
    assert binding.confidence is BindingConfidence.NONE
    assert any(d["code"] == "no_file_path" for d in binding.diagnostics)


def test_bind_alert_stale_snapshot_diagnostic(nullderef_alert: dict) -> None:
    binding = bind_alert(
        alert=nullderef_alert,
        graph_snapshot_id="g1",
        sarif_snapshot_id="g2",
    )
    assert any(d["code"] == "stale_snapshot" for d in binding.diagnostics)


def test_bind_alert_dataflow_cross_file(nullderef_alert: dict) -> None:
    alert = dict(nullderef_alert)
    alert["dataflow"] = [
        {"file_path": "src/example.py", "start_line": 10},
        {"file_path": "src/other.py", "start_line": 4},
    ]
    binding = bind_alert(
        alert=alert,
        symbol_lookup={
            ("src/example.py", 10): ["node:sym:1"],
            ("src/other.py", 4): ["node:sym:2"],
        },
    )
    assert "node:sym:2" in binding.dataflow_path_nodes
    assert "node:sym:2" in binding.cross_file_nodes


def test_bind_alert_requires_alert_id() -> None:
    with pytest.raises(ValueError):
        bind_alert(alert={})
