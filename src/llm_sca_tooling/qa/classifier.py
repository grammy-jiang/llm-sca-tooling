"""Deterministic question classifier."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.question import QuestionClass, RepoQuestion, normalize_question
from llm_sca_tooling.schemas.base import StrictBaseModel


class ClassificationResult(StrictBaseModel):
    question_id: str
    question_class: QuestionClass
    confidence: ConfidenceLabel
    derivation: str
    matched_rules: list[str] = Field(default_factory=list)
    score: float
    alternative_class: QuestionClass | None = None
    alternative_score: float | None = None


RULES: dict[QuestionClass, tuple[str, ...]] = {
    QuestionClass.FILE_LOC: (
        "where is",
        "where can i find",
        "which file",
        "what file",
        "in which file",
        "where does",
        "what path",
        "find the file",
        "locate the file",
        "implemented in",
        "defined in",
        "found in",
    ),
    QuestionClass.SYMBOL_LOC: (
        "which function",
        "which method",
        "which class",
        "which module",
        "what function",
        "what method",
        "what class",
        "who handles",
        "what handles",
        "what implements",
        "which code",
        "find the function",
        "find the class",
    ),
    QuestionClass.BEHAVIOUR_TRACE: (
        "what happens when",
        "what happens if",
        "how does",
        "trace the flow",
        "follow the call",
        "execution flow",
        "when ",
        "what is the path from",
        "walk me through",
        "how does a request reach",
        "end-to-end flow",
    ),
    QuestionClass.CONTRACT_CHECK: (
        "is ",
        " enforced",
        " satisfied",
        " comply",
        "where is this requirement",
        "where is this spec clause",
        "is there a check for",
        "how is",
        " validated",
        "which predicate",
        "does the code satisfy",
        "is the contract met",
    ),
}


def classify_question(
    question: RepoQuestion | str,
    *,
    use_llm_fallback: bool = False,
    budget_constrained: bool = False,
) -> ClassificationResult:
    repo_question = (
        normalize_question(question) if isinstance(question, str) else question
    )
    scores: dict[QuestionClass, float] = {
        question_class: 0.0
        for question_class in QuestionClass
        if question_class != QuestionClass.OTHER
    }
    matched: dict[QuestionClass, list[str]] = {
        question_class: [] for question_class in scores
    }
    text = repo_question.normalized_text.lower()
    for question_class, phrases in RULES.items():
        for phrase in phrases:
            if phrase.strip() and phrase in text:
                weight = 1.0
                if (
                    question_class == QuestionClass.CONTRACT_CHECK
                    and phrase.strip() in {"is", "how is"}
                ):
                    weight = 0.35
                scores[question_class] += weight
                matched[question_class].append(phrase.strip())
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_class, best_score = ranked[0]
    alt_class, alt_score = ranked[1]
    if best_score <= 0.0:
        return ClassificationResult(
            question_id=repo_question.question_id,
            question_class=QuestionClass.OTHER,
            confidence=ConfidenceLabel.HEURISTIC,
            derivation="deterministic",
            matched_rules=[],
            score=0.0,
        )
    if use_llm_fallback and not budget_constrained and best_score < 1.0:
        return ClassificationResult(
            question_id=repo_question.question_id,
            question_class=best_class,
            confidence=ConfidenceLabel.HEURISTIC,
            derivation="llm_fallback_disabled_stub",
            matched_rules=matched[best_class],
            score=best_score,
            alternative_class=alt_class if alt_score > 0 else None,
            alternative_score=alt_score if alt_score > 0 else None,
        )
    confidence = (
        ConfidenceLabel.PARSER if best_score >= 1.0 else ConfidenceLabel.HEURISTIC
    )
    alternative = alt_class if alt_score > 0 else None
    return ClassificationResult(
        question_id=repo_question.question_id,
        question_class=best_class,
        confidence=confidence,
        derivation="deterministic",
        matched_rules=matched[best_class],
        score=best_score,
        alternative_class=alternative,
        alternative_score=alt_score if alternative else None,
    )
