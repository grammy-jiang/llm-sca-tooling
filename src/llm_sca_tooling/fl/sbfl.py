"""Spectrum-based fault-localisation helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path

from defusedxml.ElementTree import fromstring as parse_xml_text
from defusedxml.ElementTree import parse as parse_xml
from pydantic import Field

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    RetrievalDiagnostic,
    SignalType,
)
from llm_sca_tooling.schemas.base import StrictBaseModel


class CoverageRecord(StrictBaseModel):
    file_path: str
    line_coverage: dict[int, int] = Field(default_factory=dict)
    branch_coverage: dict[str, bool] | None = None
    snapshot_id: str


def ochiai(ef: int, ep: int, nf: int, np: int) -> float:
    _ = np
    denominator = math.sqrt((ef + nf) * (ef + ep))
    if denominator == 0.0:
        return 0.0
    return ef / denominator


def parse_lcov(path: str | Path, *, snapshot_id: str = "") -> list[CoverageRecord]:
    records: list[CoverageRecord] = []
    current_file: str | None = None
    current_lines: dict[int, int] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            current_file = _normalize_path(line.removeprefix("SF:"))
            current_lines = {}
        elif line.startswith("DA:") and current_file:
            line_no, count = line.removeprefix("DA:").split(",", 1)
            current_lines[int(line_no)] = int(count)
        elif line == "end_of_record" and current_file:
            records.append(
                CoverageRecord(
                    file_path=current_file,
                    line_coverage=current_lines,
                    snapshot_id=snapshot_id,
                )
            )
            current_file = None
            current_lines = {}
    return records


def parse_cobertura(path: str | Path, *, snapshot_id: str = "") -> list[CoverageRecord]:
    tree = parse_xml(path)
    root = tree.getroot()
    if root is None:
        return []
    records: list[CoverageRecord] = []
    for class_el in root.findall(".//class"):
        filename = class_el.attrib.get("filename")
        if not filename:
            continue
        lines: dict[int, int] = {}
        for line_el in class_el.findall(".//line"):
            number = line_el.attrib.get("number")
            hits = line_el.attrib.get("hits", "0")
            if number:
                lines[int(number)] = int(hits)
        records.append(
            CoverageRecord(
                file_path=_normalize_path(filename),
                line_coverage=lines,
                snapshot_id=snapshot_id,
            )
        )
    return records


def parse_coverage_json(
    path: str | Path, *, snapshot_id: str = ""
) -> list[CoverageRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    files = payload.get("files", {})
    records: list[CoverageRecord] = []
    if not isinstance(files, dict):
        return records
    for file_path, data in files.items():
        if not isinstance(data, dict):
            continue
        executed = data.get("executed_lines", [])
        missing = data.get("missing_lines", [])
        lines: dict[int, int] = {}
        if isinstance(executed, list):
            lines.update({int(line): 1 for line in executed})
        if isinstance(missing, list):
            lines.update({int(line): 0 for line in missing})
        records.append(
            CoverageRecord(
                file_path=_normalize_path(str(file_path)),
                line_coverage=lines,
                snapshot_id=snapshot_id,
            )
        )
    return records


class SbflPrior:
    def retrieve(
        self,
        *,
        coverage_path: str | None,
        failing_tests: list[str] | None,
        repo_id: str,
        snapshot_id: str = "",
    ) -> tuple[list[CandidateFile], list[RetrievalDiagnostic]]:
        if not failing_tests:
            return [], [
                RetrievalDiagnostic(
                    code="SBFL_UNAVAILABLE",
                    message="No failing tests were provided for SBFL.",
                )
            ]
        if not coverage_path:
            return [], [
                RetrievalDiagnostic(
                    code="SBFL_UNAVAILABLE",
                    message="No coverage report was provided for SBFL.",
                )
            ]
        records = read_coverage(coverage_path, snapshot_id=snapshot_id)
        candidates = []
        for record in records:
            if not record.line_coverage:
                continue
            executed = sum(1 for count in record.line_coverage.values() if count > 0)
            if executed == 0:
                continue
            score = min(1.0, ochiai(1, max(0, executed - 1), 0, 0))
            signal = CandidateSignal(
                signal_type=SignalType.SBFL,
                raw_score=score,
                evidence=f"coverage executed {executed} lines in failing-test scope",
                confidence=ConfidenceLevel.ANALYSER,
            )
            candidates.append(
                CandidateFile(
                    candidate_id=f"candidate:file:sbfl:{repo_id}:{record.file_path}",
                    file_path=record.file_path,
                    repo_id=repo_id,
                    node_id=record.file_path,
                    signals=[signal],
                    combined_score=score,
                    confidence=ConfidenceLevel.ANALYSER,
                    evidence_summary=signal.evidence,
                    snapshot_id=record.snapshot_id,
                    is_generated=False,
                )
            )
        return candidates, []


def read_coverage(
    coverage_path: str | Path, *, snapshot_id: str = ""
) -> list[CoverageRecord]:
    path = Path(coverage_path)
    name = path.name.lower()
    if name.endswith(".lcov") or name == "lcov.info":
        return parse_lcov(path, snapshot_id=snapshot_id)
    if name.endswith(".xml"):
        return parse_cobertura(path, snapshot_id=snapshot_id)
    if name.endswith(".json"):
        return parse_coverage_json(path, snapshot_id=snapshot_id)
    return []


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    for marker in ("/src/", "/tests/", "/test/", "/lib/", "/app/"):
        if marker in normalized:
            return f"{marker.strip('/')}/{normalized.split(marker, 1)[1]}"
    return normalized.lstrip("/")


def parse_cobertura_xml_text(
    text: str, *, snapshot_id: str = ""
) -> list[CoverageRecord]:
    root = parse_xml_text(text)
    records: list[CoverageRecord] = []
    for class_el in root.findall(".//class"):
        filename = class_el.attrib.get("filename")
        if not filename:
            continue
        lines = {
            int(line_el.attrib["number"]): int(line_el.attrib.get("hits", "0"))
            for line_el in class_el.findall(".//line")
            if "number" in line_el.attrib
        }
        records.append(
            CoverageRecord(
                file_path=_normalize_path(filename),
                line_coverage=lines,
                snapshot_id=snapshot_id,
            )
        )
    return records
