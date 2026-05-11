"""Deterministic repository-question classifier."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.qa.question import QuestionClass, RepoQuestion, StrictQaModel

__all__ = ["ClassificationResult", "classify_question"]


class ClassificationResult(StrictQaModel):
    question_id: str
    question_class: QuestionClass
    confidence: str
    derivation: str = "deterministic"
    matched_rules: list[str] = Field(default_factory=list)
    score: float
    alternative_class: QuestionClass | None = None
    alternative_score: float | None = None


_RULES: dict[QuestionClass, list[str]] = {
    QuestionClass.file_loc: [
        "where is",
        "which file",
        "what file",
        "what path",
        "find the file",
        "locate",
        "defined in",
        "implemented in",
    ],
    QuestionClass.symbol_loc: [
        "which function",
        "which method",
        "which class",
        "what handles",
        "who handles",
        "find the function",
        "find the class",
    ],
    QuestionClass.behaviour_trace: [
        "what happens when",
        "what happens if",
        "how does",
        "trace the flow",
        "follow the call",
        "execution flow",
        "end-to-end",
        "walk me through",
    ],
    QuestionClass.contract_check: [
        "enforced",
        "satisfied",
        "comply",
        "requirement",
        "spec clause",
        "validated",
        "contract",
    ],
}


def classify_question(
    question: RepoQuestion, *, use_llm_fallback: bool = False
) -> ClassificationResult:
    del use_llm_fallback
    scores: dict[QuestionClass, float] = {QuestionClass.other: 0.0}
    matches: dict[QuestionClass, list[str]] = {}
    text = question.normalized_text
    for klass, rules in _RULES.items():
        matched = [rule for rule in rules if rule in text]
        if matched:
            scores[klass] = float(len(matched))
            matches[klass] = matched
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, score = ordered[0]
    if score == 0:
        winner = QuestionClass.other
    alternative = ordered[1] if len(ordered) > 1 and ordered[1][1] > 0 else None
    return ClassificationResult(
        question_id=question.question_id,
        question_class=winner,
        confidence="analyser" if score > 0 else "heuristic",
        matched_rules=matches.get(winner, []),
        score=score,
        alternative_class=alternative[0] if alternative else None,
        alternative_score=alternative[1] if alternative else None,
    )
