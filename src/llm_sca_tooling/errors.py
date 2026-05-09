"""Structured package-level error types."""

from __future__ import annotations


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


class NotImplementedFeatureError(LLMSCAError):
    """A planned feature was called before its implementation phase."""
