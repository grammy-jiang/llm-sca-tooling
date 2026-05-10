"""SARIF proximity prior for fault localisation."""

from __future__ import annotations

import re
from collections import defaultdict

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    RetrievalDiagnostic,
    SignalType,
)
from llm_sca_tooling.sarif.models import (
    NormalizedAlert,
    NormalizedSarifRun,
    NormalizedSeverity,
)
from llm_sca_tooling.storage.workspace import WorkspaceStore

_SEVERITY_WEIGHTS = {
    NormalizedSeverity.CRITICAL: 1.0,
    NormalizedSeverity.HIGH: 0.8,
    NormalizedSeverity.MEDIUM: 0.5,
    NormalizedSeverity.LOW: 0.2,
    NormalizedSeverity.INFORMATIONAL: 0.1,
}
_SECURITY_TERMS = {
    "cwe",
    "injection",
    "xss",
    "csrf",
    "sqli",
    "overflow",
    "taint",
    "secret",
    "auth",
    "authorization",
    "authentication",
    "path traversal",
}
_CWE_RE = re.compile(r"(?i)\bCWE-\d+\b")


class SarifPrior:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def retrieve(
        self, issue: IssueText, *, repo_ids: list[str]
    ) -> tuple[list[CandidateFile], list[RetrievalDiagnostic]]:
        diagnostics: list[RetrievalDiagnostic] = []
        candidates: dict[tuple[str, str], list[CandidateSignal]] = defaultdict(list)
        nodes: dict[tuple[str, str], tuple[str, str, bool]] = {}
        for repo_id in repo_ids:
            latest_snapshot = self.workspace.snapshots.get_latest_snapshot(repo_id)
            active_runs = self.workspace.sarif.list_runs(repo_id)
            if not active_runs:
                continue
            latest_run = active_runs[0]
            if (
                latest_snapshot
                and latest_run.snapshot_id != latest_snapshot.snapshot_id
            ):
                diagnostics.append(
                    RetrievalDiagnostic(
                        code="SARIF_STALE",
                        message="Most recent SARIF run predates current graph snapshot.",
                        metadata={
                            "repo_id": repo_id,
                            "run_id": latest_run.run_id,
                            "run_snapshot_id": latest_run.snapshot_id,
                            "latest_snapshot_id": latest_snapshot.snapshot_id,
                        },
                    )
                )
                continue
            for alert in latest_run.alerts:
                if alert.suppressed or not alert.file_path:
                    continue
                score, evidence = _score_alert(issue, latest_run, alert)
                if score <= 0.0:
                    continue
                key = (repo_id, alert.file_path)
                candidates[key].append(
                    CandidateSignal(
                        signal_type=SignalType.SARIF_PROXIMITY,
                        raw_score=score,
                        evidence=evidence,
                        source_refs=[alert.alert_id, latest_run.run_id],
                        confidence=ConfidenceLevel.ANALYSER,
                    )
                )
                node_id, generated = _file_node(
                    self.workspace, repo_id, alert.file_path
                )
                snapshot_id = (
                    latest_snapshot.snapshot_id
                    if latest_snapshot
                    else latest_run.snapshot_id
                )
                nodes[key] = (node_id or alert.alert_id, snapshot_id, generated)
        return [
            _candidate(repo_id, file_path, signals, nodes[(repo_id, file_path)])
            for (repo_id, file_path), signals in candidates.items()
        ], diagnostics


def _score_alert(
    issue: IssueText, run: NormalizedSarifRun, alert: NormalizedAlert
) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []
    severity = _SEVERITY_WEIGHTS[alert.normalized_severity]
    alert_text = " ".join([alert.message, alert.rule_id, alert.analyser_id]).lower()
    for error in issue.error_strings:
        if _contains_terms(alert_text, error):
            score += severity * 1.0
            reasons.append("error_string_match")
            break
    for symbol in issue.mentioned_symbols:
        if symbol.lower() in alert_text or symbol in alert.bound_symbol_node_ids:
            score += severity * 0.9
            reasons.append(f"symbol_match:{symbol}")
            break
    cwes = set(_CWE_RE.findall(issue.raw_text))
    if cwes:
        rule_cwes = {
            cwe.upper()
            for rule in run.rules
            if rule.rule_id == alert.rule_id
            for cwe in rule.cwe_ids
        }
        if {cwe.upper() for cwe in cwes} & rule_cwes:
            score += severity * 0.7
            reasons.append("cwe_match")
    if not reasons and any(term in issue.raw_text.lower() for term in _SECURITY_TERMS):
        if alert.normalized_severity in {
            NormalizedSeverity.CRITICAL,
            NormalizedSeverity.HIGH,
        }:
            score += severity * 0.3
            reasons.append("rule_family_hint")
    return min(1.0, score), "; ".join(reasons) or "sarif proximity"


def _contains_terms(haystack: str, needle: str) -> bool:
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9_-]+", needle)]
    return any(len(token) >= 4 and token in haystack for token in tokens)


def _file_node(
    workspace: WorkspaceStore, repo_id: str, file_path: str
) -> tuple[str | None, bool]:
    graph_slice = workspace.graph.fetch_by_file(repo_id, file_path)
    for node in graph_slice.nodes:
        if node.file_path == file_path and node.node_type == "file":
            return node.node_id, bool(node.properties.get("is_generated", False))
    return None, False


def _candidate(
    repo_id: str,
    file_path: str,
    signals: list[CandidateSignal],
    node_data: tuple[str, str, bool],
) -> CandidateFile:
    best = max(signal.raw_score for signal in signals)
    return CandidateFile(
        candidate_id=f"candidate:file:sarif:{repo_id}:{file_path}",
        file_path=file_path,
        repo_id=repo_id,
        node_id=node_data[0],
        signals=signals,
        combined_score=best,
        confidence=ConfidenceLevel.ANALYSER,
        evidence_summary="; ".join(signal.evidence for signal in signals[:3]),
        snapshot_id=node_data[1],
        is_generated=node_data[2],
    )
