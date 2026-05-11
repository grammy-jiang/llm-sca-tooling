"""RGFL-style reasoning-chain scaffold."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from pydantic import Field

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateReasoningEntry,
    ConfidenceLevel,
    ContextFileEntry,
)
from llm_sca_tooling.schemas.base import StrictBaseModel


class CandidateReasoningInput(StrictBaseModel):
    candidate_file: CandidateFile
    context_entry: ContextFileEntry
    issue_text: IssueText
    signals_summary: str
    graph_path_to_issue: str | None = None


class ReasoningValidation(StrictBaseModel):
    reasoning_chain: str
    evidence_citations: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    grounded: bool = True


@runtime_checkable
class FLSamplingClient(Protocol):
    """Minimal LLM sampling interface consumed by the FL reasoning scaffold."""

    def sample(self, prompt: str) -> str:
        """Return a text completion for *prompt*."""
        ...


class ReasoningChainScaffold:
    def deterministic_chain(
        self, reasoning_input: CandidateReasoningInput
    ) -> CandidateReasoningEntry:
        candidate = reasoning_input.candidate_file
        signal_parts = [
            f"{signal.signal_type.value}: {signal.evidence}"
            for signal in candidate.signals
        ]
        sarif_part = (
            f"SARIF: {len(reasoning_input.context_entry.sarif_alerts)} active alerts."
            if reasoning_input.context_entry.sarif_alerts
            else "SARIF: no matching active alerts."
        )
        graph_part = f"Graph slice: {len(reasoning_input.context_entry.graph_slice.nodes)} nodes and {len(reasoning_input.context_entry.graph_slice.edges)} edges."
        chain = " ".join([*signal_parts[:3], sarif_part, graph_part]).strip()
        if not chain:
            chain = f"No strong evidence beyond candidate ranking for {candidate.file_path}."
        return CandidateReasoningEntry(
            candidate_id=candidate.candidate_id,
            file_path=candidate.file_path,
            reasoning_chain=chain,
            derivation="deterministic",
            evidence_citations=[candidate.file_path],
        )

    def _build_reasoning_prompt(self, reasoning_input: CandidateReasoningInput) -> str:
        candidate = reasoning_input.candidate_file
        context = reasoning_input.context_entry
        sarif_count = len(context.sarif_alerts)
        graph_nodes = len(context.graph_slice.nodes)
        graph_edges = len(context.graph_slice.edges)
        signals_desc = "; ".join(
            f"{s.signal_type.value}={s.evidence}" for s in candidate.signals[:3]
        )
        return (
            f"Issue: {reasoning_input.issue_text.raw_text}\n"
            f"Candidate file: {candidate.file_path}\n"
            f"Signals: {signals_desc or 'none'}\n"
            f"SARIF alerts: {sarif_count}\n"
            f"Graph: {graph_nodes} nodes, {graph_edges} edges\n"
            f"Graph path to issue: {reasoning_input.graph_path_to_issue or 'none'}\n"
            "Explain in 2-3 sentences why this file is (or is not) the root cause."
        )

    def llm_chain(
        self,
        reasoning_input: CandidateReasoningInput,
        sampling_client: FLSamplingClient,
    ) -> CandidateReasoningEntry:
        candidate = reasoning_input.candidate_file
        prompt = self._build_reasoning_prompt(reasoning_input)
        try:
            raw_reasoning = sampling_client.sample(prompt)
        except Exception as exc:
            raw_reasoning = f"[sampling error: {exc}] Falling back to heuristic."
        validation = self.validate_llm_chain(
            raw_reasoning, reasoning_input.context_entry
        )
        return CandidateReasoningEntry(
            candidate_id=candidate.candidate_id,
            file_path=candidate.file_path,
            reasoning_chain=validation.reasoning_chain or raw_reasoning,
            derivation="llm",
            evidence_citations=validation.evidence_citations or [candidate.file_path],
        )

    def validate_llm_chain(
        self, reasoning: str, context_entry: ContextFileEntry
    ) -> ReasoningValidation:
        allowed = {context_entry.candidate_file.file_path}
        allowed.update(
            node.file_path
            for node in context_entry.graph_slice.nodes
            if node.file_path is not None
        )
        cited = set(
            re.findall(
                r"[\w@.+-]+(?:/[\w@.+-]+)+\.[A-Za-z0-9]+|[\w@.+-]+\.(?:py|js|ts|tsx|cpp|c|h|hpp)",
                reasoning,
            )
        )
        invalid = cited - allowed
        cleaned = reasoning
        for path in invalid:
            cleaned = cleaned.replace(path, "")
        diagnostics = [f"invalid_citation:{path}" for path in sorted(invalid)]
        valid_citations = sorted(cited & allowed)
        grounded = bool(valid_citations)
        if not grounded:
            diagnostics.append("ungrounded_reasoning")
        return ReasoningValidation(
            reasoning_chain=re.sub(r"\s+", " ", cleaned).strip(),
            evidence_citations=valid_citations,
            diagnostics=diagnostics,
            grounded=grounded,
        )


def downgrade_if_ungrounded(
    confidence: ConfidenceLevel, validation: ReasoningValidation
) -> ConfidenceLevel:
    if validation.grounded:
        return confidence
    return ConfidenceLevel.HEURISTIC
