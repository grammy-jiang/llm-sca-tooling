"""Blame and history prior for fault localisation."""

from __future__ import annotations

import json
import math
from pathlib import Path

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.keyword_retrieval import tokenize
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    RetrievalDiagnostic,
    SignalType,
)
from llm_sca_tooling.indexing.blame import BlameChain
from llm_sca_tooling.schemas.base import parse_utc_ts
from llm_sca_tooling.schemas.enums import ArtifactKind
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class BlamePrior:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def retrieve(
        self, issue: IssueText, *, repo_ids: list[str]
    ) -> tuple[list[CandidateFile], list[RetrievalDiagnostic]]:
        terms = set(
            tokenize(
                " ".join(
                    issue.mentioned_symbols + issue.error_strings + issue.mentioned_apis
                )
            )
        )
        diagnostics: list[RetrievalDiagnostic] = []
        candidates: list[CandidateFile] = []
        for repo_id in repo_ids:
            latest = self.workspace.snapshots.get_latest_snapshot(repo_id)
            for chain in self._chains(repo_id):
                if (
                    latest
                    and chain.git_sha
                    and latest.snapshot.git_sha
                    and chain.git_sha != latest.snapshot.git_sha
                ):
                    diagnostics.append(
                        RetrievalDiagnostic(
                            code="BLAME_STALE",
                            message="Cached blame record does not match the latest graph snapshot.",
                            metadata={"repo_id": repo_id, "file_path": chain.file_path},
                        )
                    )
                    continue
                score, evidence = _score_chain(chain, terms)
                if score <= 0.0:
                    continue
                signal = CandidateSignal(
                    signal_type=SignalType.BLAME_HISTORY,
                    raw_score=score,
                    evidence=evidence,
                    source_refs=[chain.blame_id],
                    confidence=ConfidenceLevel.HEURISTIC,
                )
                candidates.append(
                    CandidateFile(
                        candidate_id=f"candidate:file:blame:{repo_id}:{chain.file_path}",
                        file_path=chain.file_path,
                        repo_id=repo_id,
                        node_id=_file_node_id(self.workspace, repo_id, chain.file_path)
                        or chain.blame_id,
                        signals=[signal],
                        combined_score=score,
                        confidence=ConfidenceLevel.HEURISTIC,
                        evidence_summary=evidence,
                        snapshot_id=chain.snapshot_id,
                        is_generated=False,
                    )
                )
        return candidates, diagnostics

    def _chains(self, repo_id: str) -> list[BlameChain]:
        chains: list[BlameChain] = []
        for artifact in self.workspace.artifacts.list_artifacts(
            repo_id=repo_id, kind=ArtifactKind.REPORT.value
        ):
            if not artifact.artifact_id.startswith("art:blame:"):
                continue
            path = Path(artifact.uri)
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            chains.append(BlameChain.model_validate(payload))
        return chains


def _score_chain(chain: BlameChain, terms: set[str]) -> tuple[float, str]:
    summaries = [
        str(entry.summary or "") for entry in chain.line_entries if entry.summary
    ] + [str(item.get("summary") or "") for item in chain.commit_chain]
    message_tokens = set(tokenize(" ".join(summaries)))
    message_match = 1.0 if terms and terms & message_tokens else 0.0
    recency = _recency_score(chain)
    churn = min(1.0, len({entry.commit_sha for entry in chain.line_entries}) / 10.0)
    if message_match == 0.0 and recency < 0.05 and churn < 0.2:
        return 0.0, ""
    score = min(1.0, (0.4 * recency) + (0.4 * message_match) + (0.2 * churn))
    evidence_parts = []
    if message_match:
        evidence_parts.append("commit message matches issue terms")
    if recency:
        evidence_parts.append(f"recent blame score {recency:.2f}")
    if churn:
        evidence_parts.append(f"churn score {churn:.2f}")
    return score, "; ".join(evidence_parts)


def _recency_score(chain: BlameChain) -> float:
    timestamps = [
        entry.author_time for entry in chain.line_entries if entry.author_time
    ]
    timestamps.extend(
        str(item.get("author_ts"))
        for item in chain.commit_chain
        if item.get("author_ts") is not None
    )
    parsed_hours: list[float] = []
    now = parse_utc_ts(_now_ts())
    for value in timestamps:
        if value is None:
            continue
        try:
            if value.isdigit():
                seconds = int(value)
                hours = max(0.0, (now.timestamp() - seconds) / 3600.0)
            else:
                hours = max(0.0, (now - parse_utc_ts(value)).total_seconds() / 3600.0)
            parsed_hours.append(hours)
        except ValueError:
            continue
    if not parsed_hours:
        return 0.0
    return math.exp(-min(parsed_hours) / 168.0)


def _file_node_id(
    workspace: WorkspaceStore, repo_id: str, file_path: str
) -> str | None:
    graph_slice = workspace.graph.fetch_by_file(repo_id, file_path)
    for node in graph_slice.nodes:
        if node.file_path == file_path and node.node_type == "file":
            return node.node_id
    return None
