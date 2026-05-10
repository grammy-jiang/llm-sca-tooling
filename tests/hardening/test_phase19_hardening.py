from __future__ import annotations

from llm_sca_tooling.hardening.cache_invalidation import CacheInvalidationHardener
from llm_sca_tooling.hardening.cumulative_risk import CumulativeRiskMonitor
from llm_sca_tooling.hardening.git_hooks import GitHookInstaller
from llm_sca_tooling.hardening.graph_chunker import GraphChunker
from llm_sca_tooling.hardening.harness_drift import HarnessDriftChecker
from llm_sca_tooling.hardening.manifest_regression_runner import (
    ManifestRegressionRunner,
)
from llm_sca_tooling.hardening.models import (
    DriftClassification,
    HardenedPermissionMode,
)
from llm_sca_tooling.hardening.permission_profiles import (
    default_permission_profiles,
    permission_allows,
)
from llm_sca_tooling.hardening.trace_redaction_audit import TraceRedactionAuditor


def test_permission_profiles_cover_six_modes() -> None:
    profiles = default_permission_profiles()
    assert set(profiles) == set(HardenedPermissionMode)
    assert permission_allows(HardenedPermissionMode.READ_SEARCH, "search")
    assert not permission_allows(HardenedPermissionMode.READ_SEARCH, "edit")


def test_cache_invalidation_removes_stale_and_changed_keys() -> None:
    hardener = CacheInvalidationHardener()
    hardener.register_cache_key(
        "graph:file:a", repo_id="repo:1", git_sha="old", file_path="a.py"
    )
    hardener.register_cache_key(
        "graph:file:b", repo_id="repo:1", git_sha="new", file_path="b.py"
    )
    event = hardener.invalidate_for_graph_update(
        repo_id="repo:1", git_sha="new", changed_files=["b.py"]
    )
    assert event.invalidated_keys == ["graph:file:a", "graph:file:b"]
    assert hardener.verify_cache_consistency(repo_id="repo:1", git_sha="new")[
        "consistent"
    ]


def test_graph_chunker_bounds_large_graphs() -> None:
    nodes = [
        {"node_id": f"node:{index}", "file_path": f"pkg/mod{index}.py"}
        for index in range(5)
    ]
    chunks = GraphChunker(max_chunk_nodes=2).chunk(nodes)
    assert [len(chunk.node_ids) for chunk in chunks] == [2, 2, 1]
    assert chunks[0].module_prefix == "pkg"


def test_git_hook_installer_preserves_existing_content(tmp_path) -> None:
    repo = tmp_path / "repo"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "post-commit"
    hook.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")
    installer = GitHookInstaller()
    installer.install(repo)
    assert "echo existing" in hook.read_text(encoding="utf-8")
    installer.uninstall(repo)
    assert hook.exists()
    assert "evidence-sca managed hook" not in hook.read_text(encoding="utf-8")


def test_harness_drift_detects_missing_stage_record(tmp_path) -> None:
    (tmp_path / "AGENTS.md").write_text("S3 no plaintext secrets\n", encoding="utf-8")
    (tmp_path / ".agent").mkdir()
    (tmp_path / ".agent" / "plan.md").write_text("plan\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "verify.yml").write_text(
        "name: verify\n", encoding="utf-8"
    )
    records = HarnessDriftChecker().check_repo(tmp_path, expected_stage="S3")
    assert any(
        record.classification == DriftClassification.MISSING
        and record.artifact_path.endswith("harness-stage.json")
        for record in records
    )


def test_cumulative_risk_detects_repeated_tool_calls() -> None:
    events = [
        {
            "event_id": f"event:{index}",
            "type": "tool_call",
            "tool": "read",
            "args": "{}",
        }
        for index in range(4)
    ]
    findings = CumulativeRiskMonitor().detect(run_id="run:1", events=events)
    assert findings
    assert findings[0].threshold_exceeded


def test_trace_redaction_auditor_flags_sensitive_keys() -> None:
    result = TraceRedactionAuditor().audit_events(
        [{"event_id": "event:1", "payload": {"authorization": "placeholder"}}]
    )
    assert not result.passed
    assert result.findings[0]["code"] == "unredacted_secret"


def test_manifest_regression_blocks_changed_manifest() -> None:
    result = ManifestRegressionRunner().compare(
        {"schema": "0.1", "policy": "strict"},
        {"schema": "0.2", "policy": "strict"},
    )
    assert result["blocks_release"] is True
    assert result["changed_items"] == ["schema"]
