"""Filesystem-backed feedback store (Phase 16 / Gap 5)."""

from __future__ import annotations

import json
from pathlib import Path

from llm_sca_tooling.feedback.models import FeedbackRecord


class FeedbackStore:
    """Persist and retrieve FeedbackRecord objects as JSON files."""

    def __init__(self, feedback_dir: Path) -> None:
        self._dir = feedback_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def submit(self, record: FeedbackRecord) -> Path:
        """Write *record* to ``{feedback_id}.json`` and return the path."""
        path = self._dir / f"{record.feedback_id}.json"
        path.write_text(
            json.dumps(json.loads(record.model_dump_json()), indent=2),
            encoding="utf-8",
        )
        return path

    def list_records(self) -> list[FeedbackRecord]:
        """Read and return all feedback records from *feedback_dir*."""
        records: list[FeedbackRecord] = []
        for path in sorted(self._dir.glob("*.json")):
            records.append(
                FeedbackRecord.model_validate_json(path.read_text(encoding="utf-8"))
            )
        return records

    def get_weight_hints(self) -> dict[str, float]:
        """Return empty weight-hint dict (stub for future re-ranking)."""
        return {}
