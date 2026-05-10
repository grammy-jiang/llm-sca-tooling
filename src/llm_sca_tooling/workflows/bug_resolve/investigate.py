"""Investigate stage: combine FL + repo-QA into an InvestigateResult."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from llm_sca_tooling.workflows.bug_resolve.models import InvestigateResult

LocaliseCallable = Callable[[str, list[str] | None], Awaitable[dict[str, Any]]]
RepoQACallable = Callable[[str, str], Awaitable[dict[str, Any]]]


def _hash_issue(issue_text: str) -> str:
    return hashlib.sha256(issue_text.encode("utf-8")).hexdigest()[:24]


async def run_investigate(
    *,
    run_id: str,
    issue_text: str,
    repos: list[str] | None = None,
    localise: LocaliseCallable | None = None,
    repo_qa: RepoQACallable | None = None,
    snapshot_id: str | None = None,
    expected_snapshot_id: str | None = None,
    null_mode: bool = True,
) -> InvestigateResult:
    """Run the investigate stage.

    `localise` returns a dict with ``ranked_files`` (list[dict]),
    ``ranked_symbols`` (list[dict]), ``agreement_score`` (float),
    ``budget_used`` (dict), ``snapshot_id`` (str), and ``confidence`` (str).
    The null adapter fills in deterministic placeholder data.
    """
    issue_hash = _hash_issue(issue_text)
    diagnostics: list[dict[str, Any]] = []

    if localise is None:
        ranked: list[dict[str, Any]] = (
            []
            if not issue_text.strip()
            else [
                {
                    "candidate_id": "cand:0",
                    "file_path": "src/example.py",
                    "score": 0.42,
                    "signals": ["keyword"],
                }
            ]
        )
        loc_payload: dict[str, Any] = {
            "ranked_files": ranked,
            "agreement_score": 0.5 if ranked else 0.0,
            "budget_used": {"max_files": 6, "actual_files": len(ranked)},
            "snapshot_id": snapshot_id or "snap:null",
            "confidence": "heuristic" if ranked else "unknown",
        }
        if not null_mode:
            diagnostics.append(
                {"code": "no_localiser_supplied", "message": "null adapter used"}
            )
    else:
        loc_payload = await localise(issue_text, repos)

    ranked_files = list(loc_payload.get("ranked_files") or [])
    top3 = [
        str(item.get("file_path", ""))
        for item in ranked_files[:3]
        if item.get("file_path")
    ]
    agreement = float(loc_payload.get("agreement_score") or 0.0)
    snapshot = loc_payload.get("snapshot_id") or snapshot_id

    qa_answers: list[dict[str, Any]] = []
    behavioural: list[str] = []
    if repo_qa is not None and top3:
        for path in top3:
            try:
                ans = await repo_qa(f"What does {path} do?", path)
            except Exception as exc:  # pragma: no cover - defensive
                diagnostics.append({"code": "repo_qa_error", "message": str(exc)})
                continue
            qa_answers.append(ans)
            confidence = float(ans.get("confidence", 0.0))
            answer_text = str(ans.get("answer", ""))
            if confidence >= 0.5 and answer_text:
                behavioural.append(answer_text)
            else:
                diagnostics.append(
                    {
                        "code": "low_confidence_repo_qa",
                        "message": f"answer for {path} below 0.5 confidence",
                    }
                )

    stale = bool(
        expected_snapshot_id is not None
        and snapshot is not None
        and expected_snapshot_id != snapshot
    )

    return InvestigateResult(
        run_id=run_id,
        issue_text_hash=issue_hash,
        localisation_result_ref=loc_payload.get("localisation_result_ref"),
        ranked_candidates=ranked_files,
        top3_file_suspects=top3,
        repo_qa_answers=qa_answers,
        behavioural_context=behavioural,
        agreement_score=agreement,
        budget_used=dict(loc_payload.get("budget_used") or {}),
        snapshot_id=snapshot,
        stale_snapshot_flag=stale,
        confidence=str(loc_payload.get("confidence", "unknown")),
        diagnostics=diagnostics,
    )


__all__ = ["run_investigate", "LocaliseCallable", "RepoQACallable"]
