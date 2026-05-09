"""Typed SARIF ingestion errors."""

from __future__ import annotations


class SarifError(ValueError):
    """Base class for SARIF ingestion failures."""


class SarifParseError(SarifError):
    """Raised when SARIF JSON cannot be parsed."""


class SarifVersionError(SarifError):
    """Raised when a SARIF log version is unsupported."""


class AnalyserUnavailableError(SarifError):
    """Raised when a requested analyser cannot run locally."""
