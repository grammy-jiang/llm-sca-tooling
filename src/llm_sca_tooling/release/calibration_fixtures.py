"""Phase 18 calibration fixture loader.

Calibration fixtures are oracle examples that move behavioural clauses
from ``unknown`` to ``satisfied`` when the impl-check aggregator is
called with ``calibration_available=True``.

This module exposes:

- :func:`default_calibration_oracles` — every in-repo
  :class:`CalibrationOracle`, used by ``run_implementation_check`` when
  no explicit list is supplied.
- :func:`default_calibration_samples` — the underlying
  :class:`CalibrationSample` instances, consumed by
  ``release_gate.run_release_gate`` to seed the impl-check sample
  population for ECE / macro-F1 metrics.

The loader keeps an explicit list rather than auto-discovering by
filename so additions are visible at review time and the registration
order is deterministic.
"""

from __future__ import annotations

from llm_sca_tooling.release.fixtures.calibration.sarif_disappear import (
    ORACLE as SARIF_DISAPPEAR_ORACLE,
)
from llm_sca_tooling.release.models import CalibrationOracle, CalibrationSample


def default_calibration_oracles() -> list[CalibrationOracle]:
    """Return every in-repo calibration oracle.

    Update this list each time a new oracle fixture is added under
    ``release/fixtures/calibration/``.
    """
    return [SARIF_DISAPPEAR_ORACLE]


def default_calibration_samples() -> list[CalibrationSample]:
    """Return every in-repo calibration sample (oracle-derived)."""
    return [oracle.sample for oracle in default_calibration_oracles()]
