"""Harness drift classification."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.hardening.models import DriftClassification, HarnessDriftRecord


class HarnessDriftChecker:
    def check_repo(
        self, repo_path: str | Path, *, expected_stage: str = "S3"
    ) -> list[HarnessDriftRecord]:
        root = Path(repo_path)
        records = [
            self.check_file(root / "AGENTS.md", expected_stage=expected_stage),
            self.check_file(root / ".agent" / "plan.md", expected_stage=expected_stage),
            self.check_file(
                root / ".github" / "workflows" / "verify.yml",
                expected_stage=expected_stage,
            ),
        ]
        stage_path = root / ".agent" / "harness-stage.json"
        if stage_path.exists():
            text = stage_path.read_text(encoding="utf-8", errors="replace")
            if expected_stage not in text:
                records.append(
                    HarnessDriftRecord(
                        artifact_path=str(stage_path),
                        classification=DriftClassification.OUT_OF_STAGE,
                        detail="harness stage record does not match expected stage",
                    )
                )
            else:
                records.append(
                    HarnessDriftRecord(
                        artifact_path=str(stage_path),
                        classification=DriftClassification.CLEAN,
                    )
                )
        else:
            records.append(
                HarnessDriftRecord(
                    artifact_path=str(stage_path),
                    classification=DriftClassification.MISSING,
                    detail="harness stage record missing",
                )
            )
        return records

    def check_file(
        self, path: str | Path, *, expected_stage: str = "S3"
    ) -> HarnessDriftRecord:
        file_path = Path(path)
        if not file_path.exists():
            return HarnessDriftRecord(
                artifact_path=str(file_path),
                classification=DriftClassification.MISSING,
                detail="required artifact missing",
            )
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if "no plaintext secrets" in lowered and "may be relaxed" in lowered:
            return HarnessDriftRecord(
                artifact_path=str(file_path),
                classification=DriftClassification.RELAXED,
                detail="hard constraint appears relaxed",
            )
        if expected_stage not in text and "AGENTS.md" in file_path.name:
            return HarnessDriftRecord(
                artifact_path=str(file_path),
                classification=DriftClassification.STALE,
                detail="expected stage marker missing",
            )
        return HarnessDriftRecord(
            artifact_path=str(file_path),
            classification=DriftClassification.CLEAN,
        )
