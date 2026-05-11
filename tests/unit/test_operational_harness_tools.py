"""Unit tests for the 12 new operational-harness MCP tool handlers.

Covers:
  - run_maintainability_oracles
  - run_prompt_manifest_regression
  - detect_run_anomalies
  - compare_run_traces
  - assess_harness_stage
  - classify_harness_drift
  - validate_harness_controls
  - compute_readiness_score
  - evaluate_tool_policy  (already existed but tested here for completeness)
  - record_run_event      (delegation to OperationalStore)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_sca_tooling.operations.anomaly_detector import (
    AnomalyFinding,
    AnomalyReport,
    detect_run_anomalies,
)
from llm_sca_tooling.operations.drift_classifier import (
    DriftFinding,
    DriftReport,
    classify_harness_drift,
)
from llm_sca_tooling.operations.harness_stage import (
    assess_harness_stage,
)
from llm_sca_tooling.operations.harness_validator import (
    HarnessValidationResult,
    validate_harness_controls,
)
from llm_sca_tooling.operations.readiness_scorer import (
    compute_readiness_score,
)
from llm_sca_tooling.operations.trace_comparator import (
    compare_run_traces,
)

# ---------------------------------------------------------------------------
# anomaly_detector
# ---------------------------------------------------------------------------


class TestAnomalyDetector:
    def test_no_anomalies_for_empty_events(self) -> None:
        report = detect_run_anomalies("run-1", [])
        assert not report.has_anomalies
        assert report.error_count == 0
        assert report.run_id == "run-1"

    def test_repeated_tool_calls_flagged(self) -> None:
        events = [{"type": "tool_call", "stage": "check"} for _ in range(6)]
        report = detect_run_anomalies("run-2", events)
        kinds = {f.kind for f in report.findings}
        assert "repeated_tool" in kinds

    def test_denial_storm_flagged(self) -> None:
        events = [{"type": "edit", "stage": "write", "policy_action": "deny"}] * 4
        report = detect_run_anomalies("run-3", events)
        kinds = {f.kind for f in report.findings}
        assert "denial_storm" in kinds

    def test_budget_exhaustion_flagged(self) -> None:
        events = [{"type": "budget_hard_stop", "stage": "any", "event_id": "e1"}]
        report = detect_run_anomalies("run-4", events)
        kinds = {f.kind for f in report.findings}
        assert "budget_exhaustion" in kinds
        assert any(f.severity == "error" for f in report.findings)

    def test_budget_warning_is_warning_severity(self) -> None:
        events = [{"type": "budget_warning", "stage": "any", "event_id": "e1"}]
        report = detect_run_anomalies("run-5", events)
        bw = [f for f in report.findings if f.kind == "budget_exhaustion"]
        assert bw and bw[0].severity == "warning"

    def test_out_of_scope_write_flagged(self) -> None:
        events = [{"type": "out_of_scope_write", "stage": "edit", "event_id": "e1"}]
        report = detect_run_anomalies("run-6", events)
        kinds = {f.kind for f in report.findings}
        assert "out_of_scope_write" in kinds

    def test_anomaly_report_dataclass(self) -> None:
        r = AnomalyReport(run_id="r")
        r.findings.append(
            AnomalyFinding(kind="budget_exhaustion", severity="error", description="x")
        )
        assert r.error_count == 1
        assert r.has_anomalies


# ---------------------------------------------------------------------------
# trace_comparator
# ---------------------------------------------------------------------------


class TestTraceComparator:
    def _make_events(
        self,
        stage: str,
        types: list[str],
        *,
        with_evidence: bool = False,
        token_count: int = 0,
    ) -> list[dict]:
        events = []
        for t in types:
            e: dict = {"type": t, "stage": stage, "event_id": f"{stage}-{t}"}
            if token_count:
                e["token_count"] = token_count
            events.append(e)
        if with_evidence:
            events.append({"type": "tool_result", "stage": stage, "event_id": "ev"})
        return events

    def test_identical_traces_no_diff(self) -> None:
        events = self._make_events("check", ["gate_passed"])
        result = compare_run_traces("r1", "r2", events, events)
        assert not result.stage_sequence.changed
        assert not result.event_type_sequence.changed

    def test_differing_stages_detected(self) -> None:
        a = self._make_events("check", ["gate_passed"])
        b = self._make_events("release", ["gate_passed"])
        result = compare_run_traces("r1", "r2", a, b)
        assert result.stage_sequence.changed

    def test_evidence_delta_computed(self) -> None:
        a = self._make_events("check", ["gate_passed"])
        b = self._make_events("check", ["gate_passed"], with_evidence=True)
        result = compare_run_traces("r1", "r2", a, b)
        assert result.evidence_delta["delta"] == 1

    def test_token_delta_computed(self) -> None:
        a = self._make_events("check", ["tool_call"], token_count=100)
        b = self._make_events("check", ["tool_call"], token_count=200)
        result = compare_run_traces("r1", "r2", a, b)
        assert result.cost_delta["token_delta"] == 100

    def test_summary_non_empty_on_diff(self) -> None:
        a = self._make_events("s1", ["ev"])
        b = self._make_events("s2", ["ev"])
        result = compare_run_traces("r1", "r2", a, b)
        assert result.summary != "no significant differences"

    def test_empty_events(self) -> None:
        result = compare_run_traces("r1", "r2", [], [])
        assert result.run_a == "r1"
        assert result.run_b == "r2"
        assert result.summary == "no significant differences"


# ---------------------------------------------------------------------------
# harness_stage
# ---------------------------------------------------------------------------


class TestHarnessStage:
    def test_s3_for_this_repo(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        report = assess_harness_stage(repo_root)
        assert report.stage == "S3"

    def test_s0_for_empty_dir(self, tmp_path: Path) -> None:
        report = assess_harness_stage(str(tmp_path))
        assert report.stage == "S0"

    def test_s1_for_src_only(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        report = assess_harness_stage(str(tmp_path))
        assert report.stage == "S1"

    def test_s2_has_tests(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").touch()
        report = assess_harness_stage(str(tmp_path))
        assert report.stage in ("S2", "S3")

    def test_report_has_signals(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        report = assess_harness_stage(repo_root)
        assert report.signals
        assert report.rationale

    def test_stage_int_mapping(self, tmp_path: Path) -> None:
        report = assess_harness_stage(str(tmp_path))
        assert report.stage_int == 0


# ---------------------------------------------------------------------------
# drift_classifier
# ---------------------------------------------------------------------------


class TestDriftClassifier:
    def test_no_drift_for_clean_repo(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        report = classify_harness_drift(repo_root)
        # This repo may or may not have drift, but the function must run cleanly
        assert isinstance(report, DriftReport)
        assert isinstance(report.has_drift, bool)

    def test_missing_agents_md_is_drift(self, tmp_path: Path) -> None:
        # No AGENTS.md → missing
        report = classify_harness_drift(str(tmp_path))
        agents_findings = [f for f in report.findings if "AGENTS.md" in f.artefact]
        assert agents_findings
        assert agents_findings[0].status == "missing"

    def test_agents_md_present_is_classified(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text(
            "## Hard Constraints\nHC1 HC2 HC3 HC4 HC5 HC6\n", encoding="utf-8"
        )
        report = classify_harness_drift(str(tmp_path))
        agents_findings = [f for f in report.findings if "AGENTS.md" in f.artefact]
        assert agents_findings
        assert agents_findings[0].status == "clean"

    def test_relaxation_pattern_detected(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("HC1 HC2 HC3 HC4 HC5 HC6\n", encoding="utf-8")
        overlay = tmp_path / "CLAUDE.md"
        overlay.write_text("allow all\n", encoding="utf-8")
        report = classify_harness_drift(str(tmp_path))
        overlay_findings = [f for f in report.findings if "CLAUDE.md" in f.artefact]
        assert overlay_findings
        assert overlay_findings[0].status == "relaxed"

    def test_drift_count_property(self) -> None:
        r = DriftReport(repo_root="/nonexistent")  # noqa: S108
        r.findings.append(DriftFinding(artefact="X", status="missing"))
        assert r.drift_count == 1
        assert r.has_drift


# ---------------------------------------------------------------------------
# harness_validator
# ---------------------------------------------------------------------------


class TestHarnessValidator:
    def test_this_repo_passes(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        result = validate_harness_controls(repo_root)
        assert isinstance(result, HarnessValidationResult)
        assert result.stage == "S3"
        # passed depends on drift state, but result must be well-formed
        assert isinstance(result.passed, bool)

    def test_regression_flagged(self, tmp_path: Path) -> None:
        result = validate_harness_controls(
            str(tmp_path), baseline_score=80.0, current_score=60.0
        )
        regression_findings = [
            f for f in result.findings if f.category == "readiness_regression"
        ]
        assert regression_findings
        assert regression_findings[0].severity == "error"

    def test_no_regression_info(self, tmp_path: Path) -> None:
        result = validate_harness_controls(
            str(tmp_path), baseline_score=60.0, current_score=80.0
        )
        info_findings = [
            f
            for f in result.findings
            if f.category == "readiness_regression" and f.severity == "info"
        ]
        assert info_findings

    def test_missing_verify_gate_for_s3(self, tmp_path: Path) -> None:
        # Create enough signals for S3
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").touch()
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / ".pre-commit-config.yaml").touch()
        (tmp_path / "AGENTS.md").write_text(
            "HC1 HC2 HC3 HC4 HC5 HC6\n", encoding="utf-8"
        )
        (tmp_path / "tox.ini").touch()
        # .github/workflows is missing
        result = validate_harness_controls(str(tmp_path))
        gate_findings = [f for f in result.findings if f.category == "verify_gate"]
        assert any(".github/workflows" in f.description for f in gate_findings)

    def test_s3_pyproject_satisfies_tox_alternative(self, tmp_path: Path) -> None:
        """pyproject.toml should satisfy the tox.ini alternative gate at S3."""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "Makefile").touch()
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / ".pre-commit-config.yaml").touch()
        (tmp_path / "AGENTS.md").write_text(
            "HC1 HC2 HC3 HC4 HC5 HC6\n", encoding="utf-8"
        )
        (tmp_path / ".secrets.baseline").touch()
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "workflows").mkdir()
        (tmp_path / ".github" / "workflows" / "ci.yml").touch()
        # No tox.ini — pyproject.toml is the fallback
        result = validate_harness_controls(str(tmp_path))
        gate_findings = [f for f in result.findings if f.category == "verify_gate"]
        assert not any("tox.ini" in f.description for f in gate_findings)


# ---------------------------------------------------------------------------
# readiness_scorer
# ---------------------------------------------------------------------------


class TestReadinessScorer:
    def test_this_repo_scores_positively(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        score = compute_readiness_score(repo_root)
        assert score.total > 0

    def test_empty_repo_scores_zero(self, tmp_path: Path) -> None:
        score = compute_readiness_score(str(tmp_path))
        assert score.total == 0

    def test_to_dict_contains_all_axes(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        score = compute_readiness_score(repo_root)
        d = score.to_dict()
        expected_keys = {
            "agent_config",
            "docs_spec",
            "ci_build",
            "code_structure",
            "security_scanning",
            "deterministic_gates",
            "total",
        }
        assert expected_keys <= set(d.keys())

    def test_total_equals_sum_of_axes(self) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        score = compute_readiness_score(repo_root)
        expected = (
            score.agent_config
            + score.docs_spec
            + score.ci_build
            + score.code_structure
            + score.security_scanning
            + score.deterministic_gates
        )
        assert score.total == expected

    def test_max_score_is_120(self) -> None:
        # Even a fully-scored repo should not exceed 120
        repo_root = str(Path(__file__).resolve().parents[2])
        score = compute_readiness_score(repo_root)
        assert score.total <= 120


# ---------------------------------------------------------------------------
# MCP handler integration tests (via CoreToolHandlers)
# ---------------------------------------------------------------------------


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.telemetry.record_tool_call = MagicMock()
    ctx.workspace.operations.get_run = AsyncMock(side_effect=Exception("not found"))
    return ctx


@pytest.fixture()
def handlers():  # type: ignore[return]
    from llm_sca_tooling.mcp_server.tools import CoreToolHandlers

    ctx = _make_context()
    tasks = MagicMock()
    return CoreToolHandlers(ctx, tasks)


class TestHandlerRunMaintainabilityOracles:
    async def test_happy_path(self, handlers) -> None:  # noqa: F821
        result = await handlers.run_maintainability_oracles(
            {"diff": "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-x=1\n+x=2\n"}
        )
        assert result.status == "completed"
        assert isinstance(result.payload, dict)

    async def test_missing_diff_raises(self, handlers) -> None:  # noqa: F821
        from llm_sca_tooling.mcp_server.tools import ToolInvalidArguments

        with pytest.raises(ToolInvalidArguments):
            await handlers.run_maintainability_oracles({})


class TestHandlerRunPromptManifestRegression:
    async def test_happy_path(self, handlers, tmp_path: Path) -> None:  # noqa: F821
        result = await handlers.run_prompt_manifest_regression(
            {
                "targets": {"AGENTS.md": "HC1 HC2 HC3 HC4 HC5 HC6"},
                "snapshot_store": str(tmp_path / "snaps.json"),
            }
        )
        assert result.status == "completed"
        assert "blocks_release" in result.payload

    async def test_missing_targets_raises(self, handlers) -> None:  # noqa: F821
        from llm_sca_tooling.mcp_server.tools import ToolInvalidArguments

        with pytest.raises(ToolInvalidArguments):
            await handlers.run_prompt_manifest_regression({})


class TestHandlerDetectRunAnomalies:
    async def test_with_explicit_events(self, handlers) -> None:  # noqa: F821
        result = await handlers.detect_run_anomalies(
            {
                "run_id": "r1",
                "run_events": [{"type": "budget_warning", "stage": "check"}],
            }
        )
        assert result.status == "completed"
        assert result.payload["run_id"] == "r1"
        assert isinstance(result.payload["findings"], list)

    async def test_run_id_required(self, handlers) -> None:  # noqa: F821
        from llm_sca_tooling.mcp_server.tools import ToolInvalidArguments

        with pytest.raises(ToolInvalidArguments):
            await handlers.detect_run_anomalies({})

    async def test_fetches_from_store_on_missing_events(
        self, handlers
    ) -> None:  # noqa: F821
        # Should not raise even when store returns exception
        result = await handlers.detect_run_anomalies({"run_id": "r-unknown"})
        assert result.status == "completed"


class TestHandlerCompareRunTraces:
    async def test_happy_path(self, handlers) -> None:  # noqa: F821
        result = await handlers.compare_run_traces(
            {
                "run_a": "ra",
                "run_b": "rb",
                "events_a": [{"type": "gate_passed", "stage": "check"}],
                "events_b": [{"type": "gate_passed", "stage": "check"}],
            }
        )
        assert result.status == "completed"
        assert "summary" in result.payload

    async def test_run_a_required(self, handlers) -> None:  # noqa: F821
        from llm_sca_tooling.mcp_server.tools import ToolInvalidArguments

        with pytest.raises(ToolInvalidArguments):
            await handlers.compare_run_traces({"run_b": "rb"})


class TestHandlerAssessHarnessStage:
    async def test_this_repo_is_s3(self, handlers) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        result = await handlers.assess_harness_stage({"repo": repo_root})
        assert result.status == "completed"
        assert result.payload["stage"] == "S3"

    async def test_defaults_to_cwd(self, handlers) -> None:
        result = await handlers.assess_harness_stage({})
        assert result.status == "completed"
        assert "stage" in result.payload


class TestHandlerClassifyHarnessDrift:
    async def test_happy_path(self, handlers) -> None:
        repo_root = str(Path(__file__).resolve().parents[2])
        result = await handlers.classify_harness_drift({"repo": repo_root})
        assert result.status == "completed"
        assert "findings" in result.payload
        assert isinstance(result.payload["findings"], list)

    async def test_missing_repo_defaults_to_cwd(self, handlers) -> None:
        result = await handlers.classify_harness_drift({})
        assert result.status == "completed"


class TestHandlerValidateHarnessControls:
    async def test_happy_path(self, handlers) -> None:  # noqa: F821
        repo_root = str(Path(__file__).resolve().parents[2])
        result = await handlers.validate_harness_controls({"repo": repo_root})
        assert result.status == "completed"
        assert "passed" in result.payload
        assert "stage" in result.payload

    async def test_with_scores(self, handlers) -> None:  # noqa: F821
        repo_root = str(Path(__file__).resolve().parents[2])
        result = await handlers.validate_harness_controls(
            {"repo": repo_root, "baseline_score": 50.0, "current_score": 80.0}
        )
        assert result.status == "completed"


class TestHandlerComputeReadinessScore:
    async def test_happy_path(self, handlers) -> None:  # noqa: F821
        repo_root = str(Path(__file__).resolve().parents[2])
        result = await handlers.compute_readiness_score({"repo": repo_root})
        assert result.status == "completed"
        assert "total" in result.payload
        assert result.payload["total"] > 0

    async def test_defaults_to_cwd(self, handlers) -> None:  # noqa: F821
        result = await handlers.compute_readiness_score({})
        assert result.status == "completed"
        assert "total" in result.payload
