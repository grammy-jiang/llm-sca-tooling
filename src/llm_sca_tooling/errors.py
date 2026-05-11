"""Structured exception hierarchy for llm-sca-tooling."""

from __future__ import annotations

__all__ = [
    "LLMSCAError",
    "ConfigError",
    "PolicyViolationError",
    "BudgetExhaustedError",
    "PluginError",
    "SchemaValidationError",
    "ClosedRunError",
    "NotImplementedFeatureError",
]


class LLMSCAError(Exception):
    """Base exception for all llm-sca-tooling errors."""


class ConfigError(LLMSCAError):
    """Configuration is invalid or missing."""


class PolicyViolationError(LLMSCAError):
    """An operation was denied by the policy engine."""


class BudgetExhaustedError(LLMSCAError):
    """A budget limit was exceeded."""


class PluginError(LLMSCAError):
    """A plugin failed to load or execute."""


class SchemaValidationError(LLMSCAError):
    """A schema object failed validation."""


class ClosedRunError(LLMSCAError):
    """An event was appended to a run that is already closed."""


class NotImplementedFeatureError(LLMSCAError):
    """A feature that is planned but not yet implemented was called.

    Use this instead of bare NotImplementedError in skeleton modules so
    callers can distinguish a planned product feature from Python's built-in
    operator-not-supported semantics.
    """
