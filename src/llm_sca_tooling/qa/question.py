"""Question model and deterministic normalization."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field

from llm_sca_tooling.indexing.hashing import hash_text
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.workspace import _now_ts


class QuestionClass(StrEnum):
    FILE_LOC = "file-loc"
    SYMBOL_LOC = "symbol-loc"
    BEHAVIOUR_TRACE = "behaviour-trace"
    CONTRACT_CHECK = "contract-check"
    OTHER = "other"


class RepoQuestion(StrictBaseModel):
    question_id: str
    raw_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    repos: list[str] | None = None
    context: str | None = None
    snapshot_hint: str | None = None
    submitted_ts: str
    code_tokens: list[str] = Field(default_factory=list)
    repo_hints: list[str] = Field(default_factory=list)
    file_hints: list[str] = Field(default_factory=list)


_FILLER_PATTERNS = [
    r"\bcan you tell me\b",
    r"\bi was wondering\b",
    r"\bplease help me\b",
    r"\bplease\b",
]
_QUOTED_RE = re.compile(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"")
_CAMEL_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][a-z0-9]+|[a-z0-9]+)[A-Za-z0-9]*\b")
_SNAKE_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*_[a-zA-Z0-9_]+\b")
_DOTTED_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b")
_PATH_RE = re.compile(r"\b[\w.-]+(?:/[\w.-]+)+\b|\b[\w.-]+\.(?:py|pyi|ts|tsx|js|jsx|java|cc|cpp|cxx|h|hpp|idl|yaml|yml|json|toml|md)\b")


def normalize_question(raw_text: str, *, repos: list[str] | None = None, context: str | None = None, snapshot_hint: str | None = None) -> RepoQuestion:
    text = raw_text.strip()
    code_tokens = _unique(_extract_code_tokens(text))
    repo_hints = _unique(repos or _extract_repo_hints(text))
    file_hints = _unique(_PATH_RE.findall(text))

    protected: dict[str, str] = {}
    normalized = text
    for index, token in enumerate(sorted(code_tokens + file_hints, key=len, reverse=True)):
        marker = f"__CODETOKEN{index}__"
        if token in normalized:
            normalized = normalized.replace(token, marker)
            protected[marker] = token
    normalized = normalized.lower()
    for pattern in _FILLER_PATTERNS:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for marker, token in protected.items():
        normalized = normalized.replace(marker.lower(), token)

    return RepoQuestion(
        question_id=f"question:{hash_text(text, length=24)}",
        raw_text=text,
        normalized_text=normalized or text,
        repos=repo_hints or None,
        context=context,
        snapshot_hint=snapshot_hint,
        submitted_ts=_now_ts(),
        code_tokens=code_tokens,
        repo_hints=repo_hints,
        file_hints=file_hints,
    )


def _extract_code_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _QUOTED_RE.finditer(text):
        tokens.append(next(group for group in match.groups() if group))
    tokens.extend(_DOTTED_RE.findall(text))
    tokens.extend(_SNAKE_RE.findall(text))
    tokens.extend(_CAMEL_RE.findall(text))
    return tokens


def _extract_repo_hints(text: str) -> list[str]:
    hints = re.findall(r"\b(?:in repo|for service|in service)\s+([A-Za-z0-9_.-]+)", text, flags=re.IGNORECASE)
    return [hint.rstrip("?.!,") for hint in hints]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = value.strip("`'\".,?!")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique
