"""MCP Sampling availability bridge for patch review."""

from __future__ import annotations

from typing import Any


def sampling_supported(sampling: Any) -> bool:
    return bool(getattr(sampling, "status", None) == "supported")
