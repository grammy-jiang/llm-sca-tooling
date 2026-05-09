"""Path normalization and redaction helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.storage.ids import stable_hash


def normalize_root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def path_hash(path: str | Path) -> str:
    return stable_hash(str(normalize_root(path)), length=32)


def detect_vcs_type(path: Path) -> str:
    return "git" if (path / ".git").exists() else "none"


def detect_current_branch(path: Path) -> str | None:
    if detect_vcs_type(path) != "git":
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    branch = result.stdout.strip()
    return None if branch == "HEAD" else branch


def detect_default_branch(path: Path) -> str | None:
    if detect_vcs_type(path) != "git":
        return None
    for ref in ("origin/HEAD", "main", "master"):
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--abbrev-ref", ref],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        branch = result.stdout.strip().removeprefix("origin/")
        if branch and branch != "HEAD":
            return branch
    return None


def detect_remote_url_hash(path: Path) -> str | None:
    if detect_vcs_type(path) != "git":
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    remote = result.stdout.strip()
    return stable_hash(remote, length=32) if remote else None
