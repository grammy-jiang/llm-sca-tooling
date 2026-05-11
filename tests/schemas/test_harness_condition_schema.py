"""Tests for the HarnessCondition schema."""

from __future__ import annotations

from pathlib import Path

import orjson

from llm_sca_tooling.schemas.harness import (
    HarnessCondition,
    ModelBackendRef,
    RuntimeRef,
    VerificationGate,
)
from llm_sca_tooling.schemas.operations import GateStatus, GateType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"
NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


def _provenance() -> Provenance:
    return Provenance(
        source_tool="copilot-cli",
        repo=RepoRef(repo_id=REPO_ID, name="demo"),
        snapshot=SnapshotRef(
            repo_id=REPO_ID,
            git_sha="0123456789abcdef0123456789abcdef01234567",
            branch="main",
            dirty=False,
            index_status=IndexStatus.fresh,
            captured_ts=NOW,
        ),
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )


def _minimal_condition() -> HarnessCondition:
    return HarnessCondition(
        harness_condition_id="hc:test-001",
        captured_ts=NOW,
        runtime=RuntimeRef(name="copilot-cli", version="1.0.44"),
        provenance=_provenance(),
    )


def test_harness_condition_round_trip() -> None:
    cond = _minimal_condition()
    dumped = cond.model_dump_json()
    loaded = HarnessCondition.model_validate_json(dumped)
    assert loaded.harness_condition_id == "hc:test-001"
    assert loaded.permission_profile == "read-only"
    assert loaded.network_policy == "deny-by-default"


def test_harness_condition_defaults() -> None:
    cond = _minimal_condition()
    assert cond.sandbox.sandbox_type == "none"
    assert cond.retry_policy.max_retries == 3
    assert cond.exposed_tools == []
    assert cond.manifest_hashes == []


def test_harness_condition_with_gates() -> None:
    gate = VerificationGate(
        gate_name="make_verify",
        gate_type=GateType.lint,
        enabled=True,
        status=GateStatus.passed,
    )
    cond = _minimal_condition()
    cond = cond.model_copy(update={"verification_gates": [gate]})
    assert len(cond.verification_gates) == 1
    assert cond.verification_gates[0].status == GateStatus.passed


def test_harness_condition_with_model_backend() -> None:
    cond = HarnessCondition(
        harness_condition_id="hc:test-002",
        captured_ts=NOW,
        runtime=RuntimeRef(name="claude-code"),
        model_backend=ModelBackendRef(name="claude-sonnet-4-6", version="4.6"),
        provenance=_provenance(),
    )
    assert cond.model_backend is not None
    assert cond.model_backend.name == "claude-sonnet-4-6"


def test_harness_condition_schema_file_exists() -> None:
    schema_path = SCHEMAS_DIR / "harness-condition.schema.json"
    assert schema_path.exists(), "harness-condition.schema.json not found in schemas/"
    schema = orjson.loads(schema_path.read_bytes())
    required = schema.get("required", [])
    assert "harness_condition_id" in required
    assert "captured_ts" in required
