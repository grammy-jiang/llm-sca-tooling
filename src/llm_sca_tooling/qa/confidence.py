"""Evidence-derived confidence rules for repo QA."""

from __future__ import annotations

from enum import StrEnum

from llm_sca_tooling.schemas.base import StrictBaseModel


class ConfidenceLabel(StrEnum):
    UNKNOWN = "unknown"
    HEURISTIC = "heuristic"
    ANALYSER = "analyser"
    PARSER = "parser"


CONFIDENCE_RANK = {
    ConfidenceLabel.UNKNOWN: 0,
    ConfidenceLabel.HEURISTIC: 1,
    ConfidenceLabel.ANALYSER: 2,
    ConfidenceLabel.PARSER: 3,
}


def confidence_from_float(value: float) -> ConfidenceLabel:
    if value >= 0.9:
        return ConfidenceLabel.PARSER
    if value >= 0.7:
        return ConfidenceLabel.ANALYSER
    if value > 0.0:
        return ConfidenceLabel.HEURISTIC
    return ConfidenceLabel.UNKNOWN


def min_confidence(values: list[ConfidenceLabel | str]) -> ConfidenceLabel:
    if not values:
        return ConfidenceLabel.UNKNOWN
    parsed = [ConfidenceLabel(str(value)) for value in values]
    return min(parsed, key=lambda item: CONFIDENCE_RANK[item])


def cap_confidence(
    value: ConfidenceLabel | str, cap: ConfidenceLabel | str
) -> ConfidenceLabel:
    current = ConfidenceLabel(str(value))
    maximum = ConfidenceLabel(str(cap))
    return current if CONFIDENCE_RANK[current] <= CONFIDENCE_RANK[maximum] else maximum


def downgrade_confidence(value: ConfidenceLabel | str) -> ConfidenceLabel:
    current = ConfidenceLabel(str(value))
    if current == ConfidenceLabel.PARSER:
        return ConfidenceLabel.ANALYSER
    if current == ConfidenceLabel.ANALYSER:
        return ConfidenceLabel.HEURISTIC
    if current == ConfidenceLabel.HEURISTIC:
        return ConfidenceLabel.UNKNOWN
    return ConfidenceLabel.UNKNOWN


class ConfidenceDecision(StrictBaseModel):
    confidence: ConfidenceLabel
    reason: str
