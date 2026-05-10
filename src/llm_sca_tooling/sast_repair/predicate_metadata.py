"""Predicate metadata extraction (PredicateFix pattern)."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.sast_repair.models import (
    ClassificationConfidence,
    PredicateMetadata,
)

_BUILTIN_RULES: dict[str, dict[str, Any]] = {
    "py.nullderef": {
        "rule_family": "null-dereference",
        "predicate_text": "expression dereferenced without prior None check",
        "negated_predicate_text": (
            "expression guarded by a None check before dereference"
        ),
        "cwe_ids": ["CWE-476"],
        "severity": "high",
        "description": "Possible None dereference detected on the highlighted span.",
        "fix_guidance": "Add an `is not None` guard before dereferencing.",
        "known_false_positive_patterns": [
            "value previously asserted non-None in the same control-flow region"
        ],
    },
    "py.injection.subprocess": {
        "rule_family": "injection",
        "predicate_text": "user-controlled string flows into subprocess shell argument",
        "negated_predicate_text": (
            "subprocess invoked with a list of arguments and shell=False"
        ),
        "cwe_ids": ["CWE-78"],
        "severity": "critical",
        "description": "Subprocess invocation appears to receive user-controlled input.",
        "fix_guidance": (
            "Use a list of arguments and avoid shell=True; "
            "validate or escape any user-controlled component."
        ),
        "known_false_positive_patterns": [
            "input value validated against a strict allowlist before use"
        ],
    },
}


def extract_predicate_metadata(
    *,
    rule_id: str,
    sarif_rule: dict[str, Any] | None = None,
    family_table: dict[str, dict[str, Any]] | None = None,
    available_examples: int = 0,
) -> PredicateMetadata:
    """Extract :class:`PredicateMetadata` for a SARIF rule.

    Sources, in priority order:

    1. ``sarif_rule`` mapping (Phase 6 normalised rule).
    2. ``family_table`` adapter normalisation.
    3. Built-in rule database for common analyser IDs.
    4. ``unknown`` fallback.
    """
    rule_id = (rule_id or "").strip()
    if not rule_id:
        raise ValueError("rule_id is required")

    if sarif_rule:
        return PredicateMetadata(
            rule_id=rule_id,
            rule_family=str(sarif_rule.get("rule_family") or "other"),
            predicate_text=sarif_rule.get("predicate_text"),
            negated_predicate_text=sarif_rule.get("negated_predicate_text"),
            cwe_ids=list(sarif_rule.get("cwe_ids") or []),
            severity=sarif_rule.get("severity"),
            description=sarif_rule.get("description"),
            fix_guidance=sarif_rule.get("fix_guidance"),
            known_false_positive_patterns=list(
                sarif_rule.get("known_false_positive_patterns") or []
            ),
            available_examples=available_examples,
            source="sarif_rule",
            confidence=ClassificationConfidence.PARSER,
        )

    if family_table and rule_id in family_table:
        entry = family_table[rule_id]
        return PredicateMetadata(
            rule_id=rule_id,
            rule_family=str(entry.get("rule_family") or "other"),
            predicate_text=entry.get("predicate_text"),
            negated_predicate_text=entry.get("negated_predicate_text"),
            cwe_ids=list(entry.get("cwe_ids") or []),
            severity=entry.get("severity"),
            description=entry.get("description"),
            fix_guidance=entry.get("fix_guidance"),
            known_false_positive_patterns=list(
                entry.get("known_false_positive_patterns") or []
            ),
            available_examples=available_examples,
            source="family_table",
            confidence=ClassificationConfidence.ANALYSER,
        )

    if rule_id in _BUILTIN_RULES:
        entry = _BUILTIN_RULES[rule_id]
        return PredicateMetadata(
            rule_id=rule_id,
            rule_family=str(entry.get("rule_family") or "other"),
            predicate_text=entry.get("predicate_text"),
            negated_predicate_text=entry.get("negated_predicate_text"),
            cwe_ids=list(entry.get("cwe_ids") or []),
            severity=entry.get("severity"),
            description=entry.get("description"),
            fix_guidance=entry.get("fix_guidance"),
            known_false_positive_patterns=list(
                entry.get("known_false_positive_patterns") or []
            ),
            available_examples=available_examples,
            source="builtin",
            confidence=ClassificationConfidence.ANALYSER,
        )

    return PredicateMetadata(
        rule_id=rule_id,
        rule_family="other",
        available_examples=available_examples,
        source="unknown",
        confidence=ClassificationConfidence.UNKNOWN,
    )


__all__ = ["extract_predicate_metadata"]
