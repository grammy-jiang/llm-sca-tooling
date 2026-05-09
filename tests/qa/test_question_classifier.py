from __future__ import annotations

from llm_sca_tooling.qa.classifier import classify_question
from llm_sca_tooling.qa.question import QuestionClass, normalize_question


def test_question_normalization_preserves_code_tokens_and_file_hints() -> None:
    question = normalize_question("Please help me find `UserService.validate` in src/auth/views.py")
    assert "please help me" not in question.normalized_text
    assert "UserService.validate" in question.code_tokens
    assert "src/auth/views.py" in question.file_hints


def test_classifier_covers_all_phase8_classes() -> None:
    cases = {
        "Where is login implemented?": QuestionClass.FILE_LOC,
        "Which function handles authentication?": QuestionClass.SYMBOL_LOC,
        "What happens when the user submits a form?": QuestionClass.BEHAVIOUR_TRACE,
        "Is the null check enforced for user IDs?": QuestionClass.CONTRACT_CHECK,
        "Tell me about the repo.": QuestionClass.OTHER,
    }
    for text, expected in cases.items():
        assert classify_question(normalize_question(text)).question_class == expected


def test_classifier_reports_matched_rules_and_alternative() -> None:
    result = classify_question(normalize_question("Where is the function login_handler defined?"))
    assert result.matched_rules
    assert result.alternative_class is not None


def test_llm_fallback_is_disabled_stub_in_budget_mode() -> None:
    result = classify_question(normalize_question("Is auth ok?"), use_llm_fallback=True, budget_constrained=True)
    assert result.derivation == "deterministic"
