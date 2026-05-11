"""Tests for ManifestRegressionRunner."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.hardening.manifest_regression_runner import (
    ManifestRegressionRunner,
)


def test_no_snapshot_new_artefact_not_a_regression(tmp_path: Path) -> None:
    runner = ManifestRegressionRunner(snapshot_store=str(tmp_path / "snap.json"))
    report = runner.run({"output:out": '{"key":"val"}'})
    assert not report.blocks_release
    assert len(report.findings) == 0


def test_unchanged_artefact_passes(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    runner = ManifestRegressionRunner(snapshot_store=str(snap))
    runner.update_snapshots({"output:out": '{"key":"val"}'})
    report = runner.run({"output:out": '{"key":"val"}'})
    assert len(report.findings) == 0


def test_changed_artefact_flagged(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    runner = ManifestRegressionRunner(snapshot_store=str(snap))
    runner.update_snapshots({"output:out": '{"key":"val"}'})
    report = runner.run({"output:out": '{"key":"changed"}'})
    assert len(report.findings) >= 1


def test_policy_relevant_change_blocks_release(tmp_path: Path) -> None:
    snap = tmp_path / "snap.json"
    runner = ManifestRegressionRunner(snapshot_store=str(snap))
    runner.update_snapshots({"agents_hc_policy": "old content"})
    report = runner.run({"agents_hc_policy": "new content"})
    assert report.blocks_release
