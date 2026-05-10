"""Benchmark adapter contracts and shared records."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from llm_sca_tooling.evaluation.models import (
    ContaminationCanaryResult,
    FreshnessRecord,
    RDSFeatureVector,
)
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class IssueRecord(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    created_ts: str
    repo_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    source_ref: str = Field(min_length=1)
    metadata: JsonObject = Field(default_factory=dict)


class GoldPatchRecord(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    patch_text: str
    touched_files: list[str]
    patch_ref: str = Field(min_length=1)
    metadata: JsonObject = Field(default_factory=dict)


class SuspectRecord(StrictBaseModel):
    file_path: str = Field(min_length=1)
    rank: int | None = Field(default=None, ge=1)
    reason: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class AvailabilityStatus(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    available: bool
    diagnostics: list[JsonObject] = Field(default_factory=list)


class InstanceDescriptor(StrictBaseModel):
    instance_id: str = Field(min_length=1)
    suite_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)
    issue_ref: str = Field(min_length=1)
    gold_patch_ref: str = Field(min_length=1)
    gold_suspects_ref: str = Field(min_length=1)
    rds_features: RDSFeatureVector | None = None
    difficulty_tags: list[str] = Field(default_factory=list)
    contamination_canary_flag: bool = False
    available: bool = True
    created_ts: str | None = None
    metadata: JsonObject = Field(default_factory=dict)


class BenchmarkAdapter(ABC):
    suite_id: str
    suite_version: str

    @abstractmethod
    def list_instances(self) -> list[InstanceDescriptor]:
        raise NotImplementedError

    @abstractmethod
    def load_issue(self, instance_id: str) -> IssueRecord:
        raise NotImplementedError

    @abstractmethod
    def load_gold_patch(self, instance_id: str) -> GoldPatchRecord:
        raise NotImplementedError

    @abstractmethod
    def load_gold_suspects(self, instance_id: str) -> list[SuspectRecord]:
        raise NotImplementedError

    @abstractmethod
    def check_instance_availability(self, instance_id: str) -> AvailabilityStatus:
        raise NotImplementedError

    @abstractmethod
    def freshness_check(self) -> FreshnessRecord:
        raise NotImplementedError

    @abstractmethod
    def contamination_canary(
        self, eval_run_id: str, model_id: str | None = None
    ) -> ContaminationCanaryResult:
        raise NotImplementedError


def extract_changed_files(patch_text: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for raw_line in patch_text.splitlines():
        line = raw_line.strip()
        candidate: str | None = None
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                candidate = _strip_diff_prefix(parts[3])
        elif line.startswith("+++ "):
            candidate = _strip_diff_prefix(line[4:].strip())
        if candidate and candidate != "/dev/null" and candidate not in seen:
            seen.add(candidate)
            files.append(candidate)
    return files


def _strip_diff_prefix(value: str) -> str:
    if value.startswith("b/") or value.startswith("a/"):
        return value[2:]
    return value
