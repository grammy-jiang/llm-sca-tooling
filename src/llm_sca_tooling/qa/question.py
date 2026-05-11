"""Repo-QA question models and deterministic normalization."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["QuestionClass", "RepoQuestion", "normalize_question"]


class StrictQaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionClass(str, Enum):
    file_loc = "file-loc"
    symbol_loc = "symbol-loc"
    behaviour_trace = "behaviour-trace"
    contract_check = "contract-check"
    other = "other"


class RepoQuestion(StrictQaModel):
    question_id: str
    raw_text: str
    normalized_text: str
    repos: list[str] | None = None
    context: str | None = None
    snapshot_hint: str | None = None
    submitted_ts: str
    code_tokens: list[str] = Field(default_factory=list)
    file_hints: list[str] = Field(default_factory=list)


def normalize_question(
    raw_text: str,
    *,
    repos: list[str] | None = None,
    context: str | None = None,
    snapshot_hint: str | None = None,
) -> RepoQuestion:
    stripped = " ".join(raw_text.strip().split())
    lowered = stripped.lower()
    for phrase in ["can you tell me", "i was wondering", "please help me"]:
        lowered = lowered.replace(phrase, "").strip()
    tokens = _code_tokens(stripped)
    files = [token for token in tokens if "/" in token or "." in token]
    digest = hashlib.sha256(stripped.encode()).hexdigest()[:16]
    return RepoQuestion(
        question_id=f"q:{digest}",
        raw_text=raw_text,
        normalized_text=lowered,
        repos=repos,
        context=context,
        snapshot_hint=snapshot_hint,
        submitted_ts=datetime.now(UTC).isoformat(),
        code_tokens=tokens,
        file_hints=files,
    )


def _code_tokens(text: str) -> list[str]:
    quoted = re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", text)
    tokens = [next(part for part in match if part) for match in quoted]
    tokens.extend(
        re.findall(
            r"\b(?:[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_.]+|"
            r"[A-Za-z_][A-Za-z0-9_]*\.(?:py|ts|js|cc|cpp|idl)|"
            r"[A-Z][A-Za-z0-9]+|[a-z]+_[a-z0-9_]+)\b",
            text,
        )
    )
    seen: set[str] = set()
    deduped: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped
