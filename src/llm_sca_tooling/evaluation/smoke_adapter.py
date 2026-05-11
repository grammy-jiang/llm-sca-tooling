"""Local Phase 10 smoke benchmark adapter."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from llm_sca_tooling.evaluation.benchmark_adapter import (
    AvailabilityStatus,
    BenchmarkAdapter,
    GoldPatchRecord,
    InstanceDescriptor,
    IssueRecord,
    SuspectRecord,
    extract_changed_files,
)
from llm_sca_tooling.evaluation.contamination import basic_contamination_canary
from llm_sca_tooling.evaluation.models import (
    ContaminationCanaryResult,
    FreshnessRecord,
    RDSFeatureVector,
    utc_now_ts,
)
from llm_sca_tooling.schemas.base import parse_utc_ts


class LocalSmokeAdapter(BenchmarkAdapter):
    suite_id = "local-smoke"
    suite_version = "phase10-v1"

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else _default_smoke_root()

    def list_instances(self) -> list[InstanceDescriptor]:
        instances: list[InstanceDescriptor] = []
        instance_dirs = sorted(path for path in self.root.iterdir() if path.is_dir())
        for instance_dir in instance_dirs:
            issue = self.load_issue(instance_dir.name)
            rds_path = instance_dir / "rds_features.json"
            rds_features = (
                RDSFeatureVector.model_validate(
                    json.loads(rds_path.read_text(encoding="utf-8"))
                )
                if rds_path.exists()
                else None
            )
            instances.append(
                InstanceDescriptor(
                    instance_id=issue.instance_id,
                    suite_id=self.suite_id,
                    language=issue.language,
                    repo_id=issue.repo_id,
                    issue_ref=str(instance_dir / "issue.json"),
                    gold_patch_ref=str(instance_dir / "gold_patch.diff"),
                    gold_suspects_ref=str(instance_dir / "gold_suspects.json"),
                    rds_features=rds_features,
                    difficulty_tags=issue.tags,
                    contamination_canary_flag=bool(
                        issue.metadata.get("contamination_canary")
                    ),
                    available=True,
                    created_ts=issue.created_ts,
                    metadata={"fixture_dir": str(instance_dir)},
                )
            )
        return instances

    def load_issue(self, instance_id: str) -> IssueRecord:
        path = self._instance_dir(instance_id) / "issue.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("instance_id", instance_id)
        payload.setdefault("source_ref", str(path))
        return IssueRecord.model_validate(payload)

    def load_gold_patch(self, instance_id: str) -> GoldPatchRecord:
        path = self._instance_dir(instance_id) / "gold_patch.diff"
        patch_text = path.read_text(encoding="utf-8")
        return GoldPatchRecord(
            instance_id=instance_id,
            patch_text=patch_text,
            touched_files=extract_changed_files(patch_text),
            patch_ref=str(path),
        )

    def load_gold_suspects(self, instance_id: str) -> list[SuspectRecord]:
        path = self._instance_dir(instance_id) / "gold_suspects.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("suspects", []) if isinstance(payload, dict) else payload
        return [SuspectRecord.model_validate(item) for item in records]

    def check_instance_availability(self, instance_id: str) -> AvailabilityStatus:
        instance_dir = self._instance_dir(instance_id)
        missing = [
            name
            for name in ("issue.json", "gold_patch.diff")
            if not (instance_dir / name).exists()
        ]
        return AvailabilityStatus(
            instance_id=instance_id,
            available=not missing,
            diagnostics=[{"code": "missing_file", "file": name} for name in missing],
        )

    def freshness_check(self) -> FreshnessRecord:
        timestamps = [
            descriptor.created_ts
            for descriptor in self.list_instances()
            if descriptor.created_ts
        ]
        ages: list[float] = []
        parsed_timestamps = []
        now = parse_utc_ts(utc_now_ts())
        for ts in timestamps:
            parsed = parse_utc_ts(ts)
            parsed_timestamps.append(parsed)
            ages.append(max(0.0, (now - parsed).total_seconds() / 86_400))
        median_age = float(median(ages)) if ages else None
        warnings = (
            ["suite_median_age_gt_30_days"] if median_age and median_age > 30 else []
        )
        return FreshnessRecord(
            suite_id=self.suite_id,
            suite_version=self.suite_version,
            median_age_days=median_age,
            oldest_instance_ts=(
                min(parsed_timestamps).isoformat().replace("+00:00", "Z")
                if parsed_timestamps
                else None
            ),
            newest_instance_ts=(
                max(parsed_timestamps).isoformat().replace("+00:00", "Z")
                if parsed_timestamps
                else None
            ),
            last_refresh_ts=utc_now_ts(),
            warnings=warnings,
        )

    def contamination_canary(
        self, eval_run_id: str, model_id: str | None = None
    ) -> ContaminationCanaryResult:
        probe = next(
            (
                descriptor.instance_id
                for descriptor in self.list_instances()
                if descriptor.contamination_canary_flag
            ),
            None,
        )
        return basic_contamination_canary(
            eval_run_id=eval_run_id,
            model_id=model_id or "unknown",
            probe_instance_id=probe,
        )

    def _instance_dir(self, instance_id: str) -> Path:
        path = self.root / instance_id
        if not path.is_dir():
            raise FileNotFoundError(f"smoke instance not found: {instance_id}")
        return path


def _default_smoke_root() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "evaluation"
        / "fixtures"
        / "smoke"
    )
