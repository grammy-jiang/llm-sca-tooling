"""Trace contract construction and HC2 path checks."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.storage.ids import stable_hash as storage_stable_hash


def validate_command_allowlist(
    *,
    command: str,
    working_dir: str | Path,
    allowed_roots: list[str | Path],
) -> Path:
    root = Path(working_dir).expanduser().resolve()
    candidate = Path(command).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    allowed = [Path(item).expanduser().resolve() for item in allowed_roots]
    if not any(_is_relative_to(resolved, allowed_root) for allowed_root in allowed):
        raise ValueError(f"command outside allowed roots: {resolved}")
    if not resolved.exists():
        raise ValueError(f"command does not exist: {resolved}")
    return resolved


def build_environment_snapshot(
    working_dir: str | Path,
    *,
    env_keys: list[str] | None = None,
) -> JsonObject:
    root = Path(working_dir).expanduser().resolve()
    snapshot: JsonObject = {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "git_sha": _read_git_sha(root),
        "lockfile_hash": _file_hash(root / "uv.lock"),
        "sandbox": {"policy": "workspace-write"},
        "environment": {},
    }
    env_payload: JsonObject = {}
    for key in env_keys or []:
        if key in os.environ and not _looks_secret(key):
            env_payload[key] = os.environ[key]
    snapshot["environment"] = env_payload
    return snapshot


def _read_git_sha(root: Path) -> str | None:
    git_dir = root / ".git"
    head = git_dir / "HEAD"
    if not head.exists():
        return None
    content = head.read_text(encoding="utf-8", errors="replace").strip()
    if content.startswith("ref: "):
        ref_path = git_dir / content.removeprefix("ref: ").strip()
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8", errors="replace").strip()
        return None
    return content or None


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return storage_stable_hash(path.read_bytes().hex(), length=32)


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in ("token", "secret", "password", "key"))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
