"""Local smoke benchmark adapter."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.evaluation.benchmark_adapter import (
    AvailabilityStatus,
    GoldPatchRecord,
    InstanceDescriptor,
    IssueRecord,
    SuspectRecord,
)
from llm_sca_tooling.evaluation.models import FreshnessRecord

__all__ = ["LocalSmokeAdapter"]


class LocalSmokeAdapter:
    suite_id = "smoke"
    suite_version = "phase10.v1"

    def __init__(self, fixture_root: Path) -> None:
        self.fixture_root = fixture_root

    def list_instances(
        self,
        *,
        language: str | None = None,
        tag: str | None = None,
    ) -> list[InstanceDescriptor]:
        instances: list[InstanceDescriptor] = []
        if not self.fixture_root.exists():
            return instances
        for path in sorted(self.fixture_root.iterdir()):
            if not path.is_dir():
                continue
            issue = self._read_json(path / "issue.json")
            tags = list(issue.get("difficulty_tags", []))
            descriptor = InstanceDescriptor(
                instance_id=path.name,
                suite_id=self.suite_id,
                language=str(issue.get("language", "unknown")),
                repo_id=str(issue.get("repo_id", "local")),
                issue_ref=str(path / "issue.json"),
                gold_patch_ref=str(path / "gold_patch.diff"),
                gold_suspects_ref=str(path / "gold_suspects.json"),
                difficulty_tags=tags,
                contamination_canary_flag=bool(
                    issue.get("contamination_canary_flag", False)
                ),
                available=self.check_instance_availability(path.name).available,
                commit_ts=issue.get("commit_ts"),
            )
            if language and descriptor.language != language:
                continue
            if tag and tag not in tags:
                continue
            instances.append(descriptor)
        return instances

    def load_issue(self, instance_id: str) -> IssueRecord:
        path = self.fixture_root / instance_id / "issue.json"
        payload = self._read_json(path)
        return IssueRecord(
            instance_id=instance_id,
            text=str(payload["text"]),
            language=str(payload.get("language", "unknown")),
            repo_id=str(payload.get("repo_id", "local")),
            created_ts=payload.get("created_ts"),
        )

    def load_gold_patch(self, instance_id: str) -> GoldPatchRecord:
        path = self.fixture_root / instance_id / "gold_patch.diff"
        diff = path.read_text(encoding="utf-8") if path.exists() else ""
        suspects = self.load_gold_suspects(instance_id)
        return GoldPatchRecord(
            instance_id=instance_id,
            diff=diff,
            changed_files=[suspect.file_path for suspect in suspects],
        )

    def load_gold_suspects(self, instance_id: str) -> list[SuspectRecord]:
        path = self.fixture_root / instance_id / "gold_suspects.json"
        if not path.exists():
            return []
        payload = self._read_json(path)
        return [SuspectRecord(**item) for item in payload]

    def check_instance_availability(self, instance_id: str) -> AvailabilityStatus:
        path = self.fixture_root / instance_id
        required = ["issue.json", "gold_patch.diff"]
        missing = [name for name in required if not (path / name).exists()]
        return AvailabilityStatus(
            instance_id=instance_id,
            available=not missing,
            reason=f"missing {','.join(missing)}" if missing else None,
        )

    def freshness_check(self) -> FreshnessRecord:
        ages = [
            float(self._read_json(path / "issue.json").get("age_days", 0))
            for path in self.fixture_root.iterdir()
            if path.is_dir() and (path / "issue.json").exists()
        ]
        return FreshnessRecord(
            suite_id=self.suite_id,
            suite_version=self.suite_version,
            median_age_days=statistics.median(ages) if ages else 0.0,
            last_refresh_ts=None,
        )

    def _read_json(self, path: Path) -> Any:
        return orjson.loads(path.read_bytes())
