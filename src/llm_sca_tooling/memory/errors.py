"""Memory-specific errors."""

from __future__ import annotations


class MemoryBaseError(Exception):
    """Base class for governed memory errors."""


class MemoryDisabledError(MemoryBaseError):
    """Raised when memory is disabled by policy."""


class SecretDetectedError(MemoryBaseError):
    """Raised when the memory write path detects secret-like content."""


MemoryDisabled = MemoryDisabledError
SecretDetected = SecretDetectedError
