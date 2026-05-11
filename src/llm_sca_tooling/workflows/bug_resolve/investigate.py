"""Investigate stage: fault localisation + repo-QA integration."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.workflows.bug_resolve.models import InvestigateResult


def run_investigate(
    *,
    run_id: str,
    issue_text: str,
    snapshot_id: str | None = None,
    simulate_no_suspects: bool = False,
) -> InvestigateResult:
    text_hash = hashlib.sha256(issue_text.encode()).hexdigest()[:16]
    if simulate_no_suspects:
        return InvestigateResult(
            run_id=run_id,
            issue_text_hash=text_hash,
            localisation_result_ref=f"fl://empty/{run_id}",
            ranked_candidates=[],
            top3_file_suspects=[],
            confidence="unknown",
            diagnostics=["no_suspects_produced"],
        )
    # Null-mode: derive suspects from keywords in the issue text
    suspects = _keyword_suspects(issue_text)
    qa_answers = (
        [
            {
                "question": f"Is {suspects[0]} the root-cause location?",
                "answer": "likely",
                "confidence": 0.7,
                "class": "BEHAVIOUR_TRACE",
            }
        ]
        if suspects
        else []
    )
    return InvestigateResult(
        run_id=run_id,
        issue_text_hash=text_hash,
        localisation_result_ref=f"fl://result/{run_id}",
        ranked_candidates=[
            {"file_path": s, "score": 0.8 - i * 0.1, "repo_id": "target"}
            for i, s in enumerate(suspects)
        ],
        top3_file_suspects=suspects[:3],
        repo_qa_answers=qa_answers,
        behavioural_context="Null-mode behavioural context.",
        agreement_score=0.75 if suspects else 0.0,
        budget_used=100,
        snapshot_id=snapshot_id,
        stale_snapshot_flag=snapshot_id is None,
        confidence="heuristic" if suspects else "unknown",
        diagnostics=([] if suspects else ["no_suspects_produced"]),
    )


def _keyword_suspects(issue_text: str) -> list[str]:
    text = issue_text.lower()
    suspects: list[str] = []
    if "null" in text or "none" in text or "deref" in text:
        suspects.append("src/app.py")
    if "sql" in text or "injection" in text or "db" in text:
        suspects.append("src/db.py")
    if not suspects:
        suspects.append("src/main.py")
    return suspects
