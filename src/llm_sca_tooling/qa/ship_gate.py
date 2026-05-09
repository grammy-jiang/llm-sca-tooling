"""Answer quality gates and ship thresholds."""

from __future__ import annotations

from llm_sca_tooling.qa.answer import RepoAnswer
from llm_sca_tooling.qa.confidence import (
    ConfidenceLabel,
    cap_confidence,
    downgrade_confidence,
)
from llm_sca_tooling.qa.question import QuestionClass
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.workspace import WorkspaceStore


class ShipGateConfig(StrictBaseModel):
    file_loc_em_threshold: float = 0.80
    behaviour_trace_threshold: float = 0.70
    file_loc_gate_met: bool = False
    behaviour_trace_gate_met: bool = False
    stale_snapshot_tolerance_seconds: int = 3600


class GateResult(StrictBaseModel):
    passed: bool
    gate_name: str
    reason: str | None = None
    confidence_cap: ConfidenceLabel | None = None


class AnswerQualityGate:
    def check(self, answer: RepoAnswer, gate_config: ShipGateConfig) -> GateResult:
        if not answer.evidence and answer.confidence != ConfidenceLabel.UNKNOWN:
            return GateResult(
                passed=False,
                gate_name="evidence_presence",
                reason="answers above unknown require evidence",
                confidence_cap=ConfidenceLabel.UNKNOWN,
            )
        if (
            answer.question_class == QuestionClass.BEHAVIOUR_TRACE
            and not gate_config.behaviour_trace_gate_met
            and answer.confidence != ConfidenceLabel.UNKNOWN
        ):
            return GateResult(
                passed=False,
                gate_name="behaviour_trace",
                reason="behaviour trace ship gate is not met",
                confidence_cap=ConfidenceLabel.HEURISTIC,
            )
        if (
            "stale" in (answer.uncertainty or "").lower()
            or "mixed" in (answer.uncertainty or "").lower()
        ):
            return GateResult(
                passed=False,
                gate_name="stale_snapshot",
                reason="stale or mixed snapshot evidence",
                confidence_cap=downgrade_confidence(answer.confidence),
            )
        if answer.confidence == ConfidenceLabel.PARSER and not answer.graph_node_ids:
            return GateResult(
                passed=False,
                gate_name="content_snippet",
                reason="parser confidence requires graph node citations",
                confidence_cap=ConfidenceLabel.ANALYSER,
            )
        return GateResult(passed=True, gate_name="all")

    def apply(self, answer: RepoAnswer, gate_config: ShipGateConfig) -> RepoAnswer:
        result = self.check(answer, gate_config)
        if result.passed or result.confidence_cap is None:
            return answer
        capped = cap_confidence(answer.confidence, result.confidence_cap)
        data = answer.model_dump(mode="python")
        data["confidence"] = capped
        data["confidence_reason"] = (
            f"{answer.confidence_reason}; gated by {result.gate_name}: {result.reason}"
        )
        if capped == ConfidenceLabel.UNKNOWN and not data.get("recommended_action"):
            data["recommended_action"] = "Run `graph_build` to index this repository."
        return RepoAnswer.model_validate(data)


def read_ship_gate_config(workspace: WorkspaceStore) -> ShipGateConfig:
    rows = workspace.operations.query_operational_records(kind="qa_gate_config")
    if not rows:
        return ShipGateConfig()
    return ShipGateConfig.model_validate(rows[-1].payload)
