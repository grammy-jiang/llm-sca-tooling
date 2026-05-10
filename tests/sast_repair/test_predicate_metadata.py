"""Tests for predicate metadata extraction."""

from __future__ import annotations

import pytest

from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata


def test_metadata_from_sarif_rule() -> None:
    meta = extract_predicate_metadata(
        rule_id="custom.rule",
        sarif_rule={
            "rule_family": "injection",
            "predicate_text": "tainted flow",
            "negated_predicate_text": "sanitised",
            "cwe_ids": ["CWE-89"],
            "severity": "high",
        },
    )
    assert meta.source == "sarif_rule"
    assert meta.rule_family == "injection"
    assert meta.cwe_ids == ["CWE-89"]


def test_metadata_from_family_table() -> None:
    meta = extract_predicate_metadata(
        rule_id="custom.x",
        family_table={"custom.x": {"rule_family": "auth-bypass", "severity": "high"}},
    )
    assert meta.source == "family_table"
    assert meta.rule_family == "auth-bypass"


def test_metadata_from_builtin_nullderef() -> None:
    meta = extract_predicate_metadata(rule_id="py.nullderef")
    assert meta.source == "builtin"
    assert meta.rule_family == "null-dereference"
    assert meta.negated_predicate_text


def test_metadata_unknown_fallback() -> None:
    meta = extract_predicate_metadata(rule_id="totally.unknown")
    assert meta.source == "unknown"
    assert meta.rule_family == "other"


def test_metadata_requires_rule_id() -> None:
    with pytest.raises(ValueError):
        extract_predicate_metadata(rule_id="")
