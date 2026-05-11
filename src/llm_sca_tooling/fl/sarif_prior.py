"""SARIF proximity signal for fault localisation."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)

__all__ = ["sarif_prior"]

_SEVERITY = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.1}


def sarif_prior(
    issue: IssueText,
    alerts: list[Any],
    *,
    repo_id: str,
    snapshot_id: str,
) -> list[CandidateFile]:
    by_file: dict[str, float] = defaultdict(float)
    refs: dict[str, list[str]] = defaultdict(list)
    for alert in alerts:
        if bool(getattr(alert, "suppressed", False)) or getattr(
            alert, "suppression_state", None
        ):
            continue
        location = getattr(alert, "location", None)
        file_path = getattr(alert, "file_path", None) or getattr(
            location, "file_path", None
        )
        if not file_path:
            continue
        severity = getattr(alert.normalized_severity, "value", "info")
        base = _SEVERITY.get(str(severity), 0.1)
        match_weight = _match_weight(issue, alert)
        if match_weight == 0:
            continue
        by_file[file_path] += base * match_weight
        refs[file_path].append(str(alert.alert_id))
    max_score = max(by_file.values(), default=1.0)
    return [
        _candidate(
            repo_id,
            file_path,
            min(score / max_score, 1.0),
            refs[file_path],
            snapshot_id,
        )
        for file_path, score in sorted(
            by_file.items(), key=lambda item: item[1], reverse=True
        )
    ]


def _match_weight(issue: IssueText, alert: Any) -> float:
    rule = getattr(alert, "rule", None)
    haystack = " ".join(
        [
            str(getattr(alert, "message", "")),
            str(getattr(alert, "rule_id", "")),
            str(getattr(rule, "rule_id", "")),
            str(getattr(rule, "name", "")),
        ]
    ).lower()
    if any(error.lower() in haystack for error in issue.error_strings):
        return 1.0
    if any(symbol.lower() in haystack for symbol in issue.mentioned_symbols):
        return 0.9
    if re.search(r"cwe-\d+", issue.raw_text, re.I):
        return 0.7
    severity = str(getattr(alert.normalized_severity, "value", "info"))
    if issue.severity_hint == "security" and severity in {
        "critical",
        "high",
    }:
        return 0.3
    return 0.0


def _candidate(
    repo_id: str, file_path: str, score: float, refs: list[str], snapshot_id: str
) -> CandidateFile:
    signal = CandidateSignal(
        signal_type=SignalType.sarif_proximity,
        raw_score=score,
        weight=0.2,
        weighted_score=score * 0.2,
        evidence="SARIF alert matches issue terms",
        source_refs=refs,
        confidence=ConfidenceLevel.analyser,
    )
    return CandidateFile(
        candidate_id=candidate_id(repo_id, file_path, "sarif"),
        file_path=file_path,
        repo_id=repo_id,
        node_id=refs[0] if refs else file_path,
        signals=[signal],
        combined_score=score,
        confidence=ConfidenceLevel.analyser,
        evidence_summary=signal.evidence,
        snapshot_id=snapshot_id,
    )
