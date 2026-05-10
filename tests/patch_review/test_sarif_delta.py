"""Tests for sarif_delta."""

from __future__ import annotations

from llm_sca_tooling.patch_review.sarif_delta import (
    build_sarif_delta,
    empty_sarif_delta,
)


def test_empty_delta_is_unavailable() -> None:
    delta = empty_sarif_delta("d1")
    assert delta.available is False
    assert delta.new_critical_count == 0
    assert delta.new_security_count == 0
    assert any(d["code"] == "sarif_unavailable" for d in delta.diagnostics)


def test_critical_and_security_counted() -> None:
    delta = build_sarif_delta(
        "d1",
        appeared=[
            {"alert_id": "a1", "rule_id": "py/sql-injection", "severity": "critical"},
            {"alert_id": "a2", "rule_id": "noise", "severity": "low"},
            {"alert_id": "a3", "cwe": "CWE-79", "severity": "warning"},
        ],
    )
    assert delta.new_critical_count == 1
    assert delta.new_security_count == 2


def test_disappeared_severity_location_lists_preserved() -> None:
    delta = build_sarif_delta(
        "d1",
        disappeared=[{"alert_id": "g"}],
        severity_changed=[{"alert_id": "s"}],
        location_changed=[{"alert_id": "l"}],
        before_run_id="b",
        after_run_id="a",
    )
    assert delta.disappeared[0].alert_id == "g"
    assert delta.severity_changed[0].alert_id == "s"
    assert delta.location_changed[0].alert_id == "l"
    assert delta.before_run_id == "b"


def test_security_via_rule_family() -> None:
    delta = build_sarif_delta(
        "d1",
        appeared=[
            {"alert_id": "x", "rule_family": "taint-flow", "severity": "warning"}
        ],
    )
    assert delta.new_security_count == 1
