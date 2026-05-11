"""Benchmark adapter contracts."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from llm_sca_tooling.evaluation.models import (
    FreshnessRecord,
    RDSFeatureVector,
    StrictEvalModel,
)

__all__ = [
    "AvailabilityStatus",
    "BenchmarkAdapter",
    "GoldPatchRecord",
    "InstanceDescriptor",
    "IssueRecord",
    "SuspectRecord",
]


class IssueRecord(StrictEvalModel):
    instance_id: str
    text: str
    language: str
    repo_id: str
    created_ts: str | None = None


class GoldPatchRecord(StrictEvalModel):
    instance_id: str
    diff: str
    changed_files: list[str]


class SuspectRecord(StrictEvalModel):
    file_path: str
    rank: int = 1
    reason: str = "gold"


class AvailabilityStatus(StrictEvalModel):
    instance_id: str
    available: bool
    reason: str | None = None


class InstanceDescriptor(StrictEvalModel):
    instance_id: str
    suite_id: str
    language: str
    repo_id: str
    issue_ref: str
    gold_patch_ref: str
    gold_suspects_ref: str
    rds_features: RDSFeatureVector | None = None
    difficulty_tags: list[str] = Field(default_factory=list)
    contamination_canary_flag: bool = False
    available: bool = True
    commit_ts: str | None = None


class BenchmarkAdapter(Protocol):
    suite_id: str
    suite_version: str

    def list_instances(self) -> list[InstanceDescriptor]: ...
    def load_issue(self, instance_id: str) -> IssueRecord: ...
    def load_gold_patch(self, instance_id: str) -> GoldPatchRecord: ...
    def load_gold_suspects(self, instance_id: str) -> list[SuspectRecord]: ...
    def check_instance_availability(self, instance_id: str) -> AvailabilityStatus: ...
    def freshness_check(self) -> FreshnessRecord: ...
