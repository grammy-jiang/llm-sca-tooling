"""Spectrum-based fault localisation helpers."""

from __future__ import annotations

import math
import re
from pathlib import Path

from defusedxml import ElementTree  # type: ignore[import-untyped]

from llm_sca_tooling.fl.models import StrictFlModel

__all__ = ["CoverageRecord", "ochiai", "parse_cobertura", "parse_lcov"]


class CoverageRecord(StrictFlModel):
    file_path: str
    line_coverage: dict[int, int]
    branch_coverage: dict[str, bool] | None = None
    snapshot_id: str | None = None


def ochiai(ef: int, ep: int, nf: int, np: int) -> float:
    del np
    denominator = math.sqrt((ef + nf) * (ef + ep))
    return 0.0 if denominator == 0 else ef / denominator


def parse_lcov(path: Path, snapshot_id: str | None = None) -> list[CoverageRecord]:
    records: list[CoverageRecord] = []
    current_file: str | None = None
    coverage: dict[int, int] = {}
    for line in path.read_text().splitlines():
        if line.startswith("SF:"):
            current_file = line[3:]
            coverage = {}
        elif line.startswith("DA:"):
            line_no, count = line[3:].split(",", 1)
            coverage[int(line_no)] = int(count)
        elif line == "end_of_record" and current_file:
            records.append(
                CoverageRecord(
                    file_path=current_file,
                    line_coverage=coverage,
                    snapshot_id=snapshot_id,
                )
            )
    return records


def parse_cobertura(path: Path, snapshot_id: str | None = None) -> list[CoverageRecord]:
    root = ElementTree.fromstring(path.read_text())
    records: list[CoverageRecord] = []
    for klass in root.findall(".//class"):
        filename = klass.attrib.get("filename")
        if not filename:
            continue
        coverage = {
            int(line.attrib["number"]): int(float(line.attrib.get("hits", "0")))
            for line in klass.findall(".//line")
            if re.match(r"\d+", line.attrib.get("number", ""))
        }
        records.append(
            CoverageRecord(
                file_path=filename, line_coverage=coverage, snapshot_id=snapshot_id
            )
        )
    return records
