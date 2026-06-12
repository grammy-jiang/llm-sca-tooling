"""LLM-boundary hindsight relabeller (phase 17 §9, Agent-HER).

The LLM call is injected as a plain ``complete: (prompt) -> response`` callable
so this module carries no network or provider dependency (HC5: deny-by-default
egress). The caller owns transport, authentication, and model selection.

The relabeller never upgrades trust on its own: unparseable or out-of-vocabulary
LLM output falls back to the original outcome with ``confidence: unknown``, and
every label is emitted as an unreviewed hypothesis.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from llm_sca_tooling.memory.models import HindsightLabel, TrajectoryRecord

_ALLOWED_OUTCOMES = frozenset(
    {"resolved", "resolved_with_risk", "no_fix_found", "uncertain"}
)
_ALLOWED_UTILITIES = frozenset({"high", "medium", "low", "unknown"})
_ALLOWED_CONFIDENCES = frozenset({"high", "medium", "low", "unknown"})

_PROMPT_TEMPLATE = """\
You are reviewing a failed or inconclusive repair trajectory for hindsight \
relabelling (Agent-HER). Decide whether the trajectory, although it did not \
achieve its original goal, demonstrates a useful pattern for the candidate \
goal below.

trajectory_id: {trajectory_id}
workflow_type: {workflow_type}
issue_class: {issue_class}
original_outcome: {outcome}
original_utility: {utility}
patch_class: {patch_class}
sarif_delta_summary: {sarif_delta}
test_delta_summary: {test_delta}

candidate_goal: {candidate_goal}

Respond with a single JSON object and nothing else:
{{"relabelled_outcome": "resolved|resolved_with_risk|no_fix_found|uncertain",
 "relabelled_utility": "high|medium|low|unknown",
 "confidence": "high|medium|low|unknown",
 "evidence_refs": ["<artefact references that justify the relabel>"]}}
"""


class LLMHindsightRelabeller:
    """Hindsight relabeller backed by an injected LLM completion callable."""

    version = "phase17.v1"

    def __init__(
        self,
        *,
        complete: Callable[[str], str],
        model_id: str,
    ) -> None:
        self._complete = complete
        self.model_id = model_id

    def relabel(
        self,
        trajectory: TrajectoryRecord,
        candidate_goal: str,
    ) -> HindsightLabel:
        prompt = _PROMPT_TEMPLATE.format(
            trajectory_id=trajectory.trajectory_id,
            workflow_type=trajectory.workflow_type,
            issue_class=trajectory.issue_class,
            outcome=trajectory.outcome,
            utility=trajectory.utility,
            patch_class=trajectory.patch_class or "unknown",
            sarif_delta=trajectory.sarif_delta_summary or "none",
            test_delta=trajectory.test_delta_summary or "none",
            candidate_goal=candidate_goal,
        )
        raw = self._complete(prompt)
        parsed = self._parse_response(raw)

        outcome = parsed.get("relabelled_outcome")
        if outcome not in _ALLOWED_OUTCOMES:
            outcome = trajectory.outcome
        utility = parsed.get("relabelled_utility")
        if utility not in _ALLOWED_UTILITIES:
            utility = "unknown"
        confidence = parsed.get("confidence")
        if confidence not in _ALLOWED_CONFIDENCES:
            confidence = "unknown"
        refs_raw = parsed.get("evidence_refs")
        evidence_refs = (
            [ref for ref in refs_raw if isinstance(ref, str)]
            if isinstance(refs_raw, list)
            else []
        )

        return HindsightLabel(
            trajectory_id=trajectory.trajectory_id,
            original_outcome=trajectory.outcome,
            relabelled_goal=candidate_goal,
            relabelled_outcome=outcome,
            relabelled_utility=utility,
            confidence=confidence,
            evidence_refs=evidence_refs,
            generator_model=self.model_id,
            review_state="unreviewed",
        )

    @staticmethod
    def _parse_response(raw: str) -> dict[str, object]:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
