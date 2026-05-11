"""Tests for RDS v0.2 feature computation helpers."""

from __future__ import annotations

from llm_sca_tooling.evaluation.benchmark_adapter import (
    GoldPatchRecord,
    InstanceDescriptor,
    IssueRecord,
)
from llm_sca_tooling.evaluation.rds_features import (
    _compute_chain_depth,
    _compute_cross_file_dataflow,
    _compute_memorisation_distance,
    _compute_test_brittleness,
    compute_rds_features,
)


def _make_descriptor(metadata: dict | None = None) -> InstanceDescriptor:
    return InstanceDescriptor(
        instance_id="inst:test",
        suite_id="test-suite",
        language="python",
        repo_id="repo:test",
        issue_ref="issue:1",
        gold_patch_ref="patch:1",
        gold_suspects_ref="suspects:1",
        metadata=metadata or {},
    )


def _make_gold_patch(files: list[str] | None = None) -> GoldPatchRecord:
    return GoldPatchRecord(
        instance_id="inst:test",
        patch_text="diff --git a/foo.py b/foo.py\n@@ -1 +1 @@\n-old\n+new\n",
        touched_files=files or ["src/foo.py"],
        patch_ref="patch:test",
    )


def _make_issue() -> IssueRecord:
    return IssueRecord(
        instance_id="inst:test",
        title="Test issue",
        body="test body",
        created_ts="2024-01-01T00:00:00Z",
        repo_id="repo:test",
        language="python",
        source_ref="commit:abc123",
    )


def test_chain_depth_returns_none_without_conn() -> None:
    result = _compute_chain_depth(None, "inst:test", _make_gold_patch())
    assert result is None


def test_cross_file_dataflow_returns_none_without_conn() -> None:
    result = _compute_cross_file_dataflow(None, _make_gold_patch())
    assert result is None


def test_cross_file_dataflow_returns_none_for_empty_files() -> None:
    result = _compute_cross_file_dataflow(None, _make_gold_patch(files=[]))
    assert result is None


def test_test_brittleness_returns_none_without_conn() -> None:
    result = _compute_test_brittleness(None, "inst:test")
    assert result is None


def test_memorisation_distance_defaults() -> None:
    dist, calibrated = _compute_memorisation_distance(_make_descriptor())
    assert dist == 0.5
    assert calibrated is False


def test_memorisation_distance_from_metadata() -> None:
    desc = _make_descriptor(
        metadata={"memorisation_distance": 0.8, "memorisation_calibrated": True}
    )
    dist, calibrated = _compute_memorisation_distance(desc)
    assert dist == 0.8
    assert calibrated is True


def test_memorisation_distance_handles_bad_metadata() -> None:
    desc = _make_descriptor(metadata={"memorisation_distance": "not_a_float"})
    dist, calibrated = _compute_memorisation_distance(desc)
    assert dist == 0.5
    assert calibrated is False


def test_compute_rds_features_without_conn() -> None:
    descriptor = _make_descriptor()
    issue = _make_issue()
    gold_patch = _make_gold_patch()
    vec = compute_rds_features(
        eval_run_id="eval:test",
        descriptor=descriptor,
        issue=issue,
        gold_patch=gold_patch,
        conn=None,
    )
    assert vec.instance_id == "inst:test"
    assert vec.eval_run_id == "eval:test"
    assert vec.files_touched == 1
    assert vec.chain_depth is None
    assert vec.cross_file_dataflow is None
    assert vec.test_brittleness is None
    assert vec.memorisation_distance == 0.5
    assert vec.memorisation_calibrated is False
    assert "rds_version" in vec.provenance
    assert vec.provenance["rds_version"] == "0.2"
    assert "chain_depth" in vec.diagnostics


def test_compute_rds_features_with_metadata_distance() -> None:
    descriptor = _make_descriptor(
        metadata={"memorisation_distance": 0.3, "memorisation_calibrated": True}
    )
    issue = _make_issue()
    gold_patch = _make_gold_patch()
    vec = compute_rds_features(
        eval_run_id="eval:test",
        descriptor=descriptor,
        issue=issue,
        gold_patch=gold_patch,
    )
    assert vec.memorisation_distance == 0.3
    assert vec.memorisation_calibrated is True


def test_compute_rds_features_counts_unique_files() -> None:
    descriptor = _make_descriptor()
    issue = _make_issue()
    gold_patch = _make_gold_patch(files=["src/a.py", "src/b.py", "src/a.py"])
    vec = compute_rds_features(
        eval_run_id="eval:test",
        descriptor=descriptor,
        issue=issue,
        gold_patch=gold_patch,
    )
    assert vec.files_touched == 2
