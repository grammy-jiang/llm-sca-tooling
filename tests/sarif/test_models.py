"""Unit tests for SARIF models."""

from __future__ import annotations

from llm_sca_tooling.sarif.models import (
    NormalizedSeverity,
    SarifLog,
)


def test_normalized_severity_order() -> None:
    order = [
        NormalizedSeverity.CRITICAL,
        NormalizedSeverity.HIGH,
        NormalizedSeverity.MEDIUM,
        NormalizedSeverity.LOW,
        NormalizedSeverity.INFORMATIONAL,
    ]
    # Just verify they are distinct enum members
    assert len(set(order)) == len(order)


def test_sarif_log_parse_minimal() -> None:
    raw = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "TestTool", "rules": []}},
                "results": [],
            }
        ],
    }
    log = SarifLog.model_validate(raw)
    assert log.version == "2.1.0"
    assert len(log.runs) == 1
    assert log.runs[0].tool.driver.name == "TestTool"
