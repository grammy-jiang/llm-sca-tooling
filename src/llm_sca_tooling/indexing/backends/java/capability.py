"""Java backend capability flag."""

from __future__ import annotations

import os

__all__ = ["JAVA_BACKEND_ENABLED", "java_backend_enabled"]


def java_backend_enabled() -> bool:
    return os.environ.get("LLM_SCA_JAVA_BACKEND_ENABLED") == "1"


JAVA_BACKEND_ENABLED = java_backend_enabled()
