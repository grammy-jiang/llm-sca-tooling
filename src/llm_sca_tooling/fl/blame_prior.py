"""Blame and history prior for fault localisation."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)
from llm_sca_tooling.qa.blame import BlameEntry

__all__ = ["blame_prior", "recency_decay"]


def blame_prior(
    issue: IssueText, entries: list[BlameEntry], *, snapshot_id: str | None = None
) -> list[CandidateFile]:
    terms = [
        *issue.mentioned_symbols,
        *issue.error_strings,
        *issue.mentioned_apis,
        *re.findall(r"[A-Za-z_][A-Za-z0-9_]+", issue.normalized_text),
    ]
    by_file: dict[tuple[str, str], float] = defaultdict(float)
    refs: dict[tuple[str, str], list[str]] = defaultdict(list)
    churn = Counter((entry.repo_id, entry.file_path) for entry in entries)
    for entry in entries:
        key = (entry.repo_id, entry.file_path)
        summary_match = any(
            term.lower() in entry.commit.summary.lower() for term in terms
        )
        if not summary_match and churn[key] <= 1:
            continue
        score = 0.4 * recency_decay(entry.commit.author_time)
        score += 0.4 if summary_match else 0.0
        score += 0.2 * min(churn[key] / max(churn.values(), default=1), 1.0)
        by_file[key] = max(by_file[key], score)
        refs[key].append(entry.commit.commit_sha)
    return [
        _candidate(
            repo_id,
            file_path,
            min(score, 1.0),
            refs[(repo_id, file_path)],
            snapshot_id or "",
        )
        for (repo_id, file_path), score in sorted(
            by_file.items(), key=lambda item: item[1], reverse=True
        )
    ]


def recency_decay(author_time: str) -> float:
    try:
        commit_time = datetime.fromtimestamp(int(author_time), UTC)
    except ValueError:
        try:
            commit_time = datetime.fromisoformat(author_time)
        except ValueError:
            return 0.0
    hours = max((datetime.now(UTC) - commit_time).total_seconds() / 3600, 0.0)
    return math.exp(-hours / 168)


def _candidate(
    repo_id: str, file_path: str, score: float, refs: list[str], snapshot_id: str
) -> CandidateFile:
    signal = CandidateSignal(
        signal_type=SignalType.blame_history,
        raw_score=score,
        weight=0.1,
        weighted_score=score * 0.1,
        evidence="recent blame/history matches issue terms",
        source_refs=refs,
        confidence=ConfidenceLevel.heuristic,
    )
    return CandidateFile(
        candidate_id=candidate_id(repo_id, file_path, "blame"),
        file_path=file_path,
        repo_id=repo_id,
        node_id=file_path,
        signals=[signal],
        combined_score=score,
        confidence=ConfidenceLevel.heuristic,
        evidence_summary=signal.evidence,
        snapshot_id=snapshot_id,
    )
