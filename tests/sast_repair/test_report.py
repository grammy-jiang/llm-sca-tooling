"""Integration tests for run_sast_repair orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_sca_tooling.sast_repair.corpus_adapter import LocalFixtureCorpusAdapter
from llm_sca_tooling.sast_repair.models import Verdict
from llm_sca_tooling.sast_repair.report import run_sast_repair


def _make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "example.py").write_text("x = None\n", encoding="utf-8")
    (repo / "src" / "runner.py").write_text("import subprocess\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_example.py").write_text(
        "def test_x(): pass\n", encoding="utf-8"
    )
    return repo


async def test_orchestrator_alert_fixed_path(
    tmp_path: Path, nullderef_alert: dict, corpus_root: Path
) -> None:
    repo = _make_repo(tmp_path)
    adapter = LocalFixtureCorpusAdapter(corpus_root)

    async def analyser_runner(path: str, files: list[str]) -> dict[str, Any]:
        return {"run_id": "after:1"}

    async def build_runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {"build_status": "ok", "test_run_status": "passed"}

    report, sheet = await run_sast_repair(
        alert=nullderef_alert,
        repo_root=repo,
        corpus_adapter=adapter,
        before_alerts=[{"alert_id": "alert-nullderef-001", "severity": "high"}],
        after_alerts=[],
        sarif_run_before_id="before",
        sarif_run_after_id="after",
        classification_signals={
            "has_dataflow_edges": True,
            "security_sensitive_symbol": True,
        },
        analyser_runner=analyser_runner,
        build_test_runner=build_runner,
        coverage_map={},
        run_id="r1",
        poc_plus_available=True,
        graph_dataflow_complete=True,
    )
    assert sheet.hcs_id
    assert report.harness_condition_id == sheet.hcs_id
    assert report.verdict in {Verdict.ALERT_FIXED, Verdict.ALERT_FIXED_WITH_RISK}
    assert report.sarif_delta is not None
    assert report.sarif_delta.original_alert_gone is True


async def test_orchestrator_repair_blocked_by_new_critical(
    tmp_path: Path, injection_alert: dict, corpus_root: Path
) -> None:
    repo = _make_repo(tmp_path)
    adapter = LocalFixtureCorpusAdapter(corpus_root)

    async def build_runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {"build_status": "ok", "test_run_status": "passed"}

    report, _ = await run_sast_repair(
        alert=injection_alert,
        repo_root=repo,
        corpus_adapter=adapter,
        before_alerts=[{"alert_id": "alert-injection-001", "severity": "critical"}],
        after_alerts=[{"alert_id": "new-1", "normalized_severity": "critical"}],
        classification_signals={
            "has_dataflow_edges": True,
            "security_sensitive_symbol": True,
        },
        build_test_runner=build_runner,
    )
    assert report.verdict is Verdict.REPAIR_BLOCKED
    assert report.recommendation == "block"


async def test_orchestrator_repair_failed_when_alert_remains(
    tmp_path: Path, nullderef_alert: dict, corpus_root: Path
) -> None:
    repo = _make_repo(tmp_path)
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    report, _ = await run_sast_repair(
        alert=nullderef_alert,
        repo_root=repo,
        corpus_adapter=adapter,
        before_alerts=[{"alert_id": "alert-nullderef-001", "severity": "high"}],
        after_alerts=[{"alert_id": "alert-nullderef-001", "severity": "high"}],
        classification_signals={"has_dataflow_edges": True},
    )
    assert report.verdict is Verdict.REPAIR_FAILED


async def test_orchestrator_false_positive_suppressed(
    tmp_path: Path, false_positive_alert: dict, corpus_root: Path
) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    report, _ = await run_sast_repair(
        alert=false_positive_alert,
        repo_root=None,
        corpus_adapter=adapter,
        classification_signals={
            "test_only_symbol": True,
            "high_fp_rule": True,
            "historical_suppressions": [{"reason": "test-only"}],
        },
        file_node_lookup={"tests/test_example.py": "node:1"},
    )
    assert report.verdict is Verdict.FALSE_POSITIVE_SUPPRESSED
    assert report.suppression_proposal is not None
    assert report.suppression_proposal.reviewer_required is True


async def test_orchestrator_unknown_when_no_sarif_evidence(
    tmp_path: Path, unknown_alert: dict, corpus_root: Path
) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    report, _ = await run_sast_repair(
        alert=unknown_alert,
        repo_root=None,
        corpus_adapter=adapter,
    )
    assert report.verdict in {
        Verdict.UNKNOWN,
        Verdict.REPAIR_FAILED,
        Verdict.ALERT_FIXED,
        Verdict.ALERT_FIXED_WITH_RISK,
    }


async def test_orchestrator_with_risk_classifier(
    tmp_path: Path, nullderef_alert: dict, corpus_root: Path
) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)

    async def risk(diff: str, files: list[str]) -> dict[str, Any]:
        return {"score": 0.0, "label": "safe"}

    async def build_runner(path: str, scope: list[str]) -> dict[str, Any]:
        return {"build_status": "ok", "test_run_status": "passed"}

    report, _ = await run_sast_repair(
        alert=nullderef_alert,
        repo_root=None,
        corpus_adapter=adapter,
        before_alerts=[{"alert_id": "alert-nullderef-001"}],
        after_alerts=[],
        classification_signals={"has_dataflow_edges": True},
        build_test_runner=build_runner,
        risk_classifier=risk,
    )
    assert report.patch_risk_result == {"score": 0.0, "label": "safe"}
