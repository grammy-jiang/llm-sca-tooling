"""Task ID generation."""

from __future__ import annotations

import secrets


def new_task_id() -> str:
    return f"task:{secrets.token_urlsafe(32)}"
