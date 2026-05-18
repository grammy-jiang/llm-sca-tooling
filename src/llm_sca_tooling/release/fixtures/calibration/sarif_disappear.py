"""First Phase 18 calibration fixture — SARIF disappear.

The clause "The original alert must disappear before the alert is
considered fixed." is a behavioural obligation: it requires that a
SARIF alert which existed before a fix is *gone* in the after-state.
The implementation lives at:

- ``src/llm_sca_tooling/sarif/delta.py::compute_sarif_delta`` — computes
  appeared / disappeared / changed alert sets between two SARIF
  documents.
- ``src/llm_sca_tooling/sarif/delta.py::_change_type`` — labels each
  alert as appeared / disappeared / changed.

This oracle asserts the implementation satisfies the behavioural clause
when ``calibration_available=True``.  The substring
``"alert must disappear"`` is the matching condition; any spec line
containing that phrase is considered satisfied by this fixture.

Fixture-format note (per Plan 03): this fixture is F-inline (Python
constant).  Once the corpus reaches ≥3 fixtures the format should be
revisited; YAML/JSONL would scale better for Track C's
production-derived refresh.
"""

from __future__ import annotations

from llm_sca_tooling.release.models import CalibrationOracle, CalibrationSample

ORACLE = CalibrationOracle(
    sample=CalibrationSample(
        sample_id="sarif-disappear:fixture-001",
        family="behavioural:sarif-disappear",
        predicted_probability=0.95,
        predicted_label="satisfied",
        gold_label="satisfied",
    ),
    clause_text_pattern="alert must disappear",
)
