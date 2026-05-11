"""Repo-QA answer quality gates."""

from __future__ import annotations

from llm_sca_tooling.qa.answer import RepoAnswer, recommended_action
from llm_sca_tooling.qa.question import QuestionClass, StrictQaModel

__all__ = ["AnswerQualityGate", "GateResult", "ShipGateConfig"]


class ShipGateConfig(StrictQaModel):
    file_loc_em_threshold: float = 0.80
    behaviour_trace_threshold: float = 0.70
    file_loc_gate_met: bool = False
    behaviour_trace_gate_met: bool = False
    stale_snapshot_tolerance_seconds: int = 3600


class GateResult(StrictQaModel):
    passed: bool
    gate_name: str
    reason: str | None = None
    confidence_cap: str | None = None


class AnswerQualityGate:
    def check(self, answer: RepoAnswer, config: ShipGateConfig) -> list[GateResult]:
        results: list[GateResult] = []
        results.append(
            GateResult(
                passed=answer.confidence == "unknown" or bool(answer.evidence),
                gate_name="evidence_presence",
                reason=None if answer.evidence else "answer has no evidence",
                confidence_cap="unknown" if not answer.evidence else None,
            )
        )
        if answer.question_class == QuestionClass.behaviour_trace:
            passed = config.behaviour_trace_gate_met or answer.confidence in {
                "unknown",
                "heuristic",
            }
            results.append(
                GateResult(
                    passed=passed,
                    gate_name="behaviour_trace",
                    reason=None if passed else "behaviour trace ship gate is not met",
                    confidence_cap="heuristic" if not passed else None,
                )
            )
        stale = (
            answer.uncertainty is not None and "snapshot" in answer.uncertainty.lower()
        )
        results.append(
            GateResult(
                passed=not stale,
                gate_name="stale_snapshot",
                reason="mixed or stale snapshot evidence" if stale else None,
                confidence_cap="analyser" if stale else None,
            )
        )
        snippet_only = bool(answer.evidence) and all(
            ev.node_id is None and ev.content_snippet for ev in answer.evidence
        )
        results.append(
            GateResult(
                passed=answer.confidence != "parser" or not snippet_only,
                gate_name="content_snippet",
                reason=(
                    "parser confidence requires graph nodes" if snippet_only else None
                ),
                confidence_cap="heuristic" if snippet_only else None,
            )
        )
        return results

    def apply(self, answer: RepoAnswer, config: ShipGateConfig) -> RepoAnswer:
        confidence = answer.confidence
        uncertainty = answer.uncertainty
        for result in self.check(answer, config):
            if result.confidence_cap is not None:
                confidence = _min_confidence(confidence, result.confidence_cap)
                uncertainty = uncertainty or result.reason
        if confidence == answer.confidence and uncertainty == answer.uncertainty:
            return answer
        data = answer.model_dump(mode="python")
        data["confidence"] = confidence
        data["uncertainty"] = uncertainty
        if confidence == "unknown":
            data["recommended_action"] = (
                answer.recommended_action or recommended_action(answer.question_class)
            )
            data["graph_node_ids"] = []
        return RepoAnswer.model_validate(data)


_ORDER = {"unknown": 0, "heuristic": 1, "analyser": 2, "parser": 3}


def _min_confidence(left: str, right: str) -> str:
    return left if _ORDER[left] <= _ORDER[right] else right
