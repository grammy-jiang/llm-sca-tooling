"""Locate packaged skill data (SKILL.md, references/).

The package ships a copy of all skills under
``llm_sca_tooling/skill_data/<skill-name>/``.  This module finds the skill
data whether installed as a wheel or used in editable mode.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

_PACKAGE = "llm_sca_tooling"
_DATA_SUBDIR = "skill_data"

#: Names of all bundled skills.
SKILL_NAMES: tuple[str, ...] = (
    "audit",
    "fix",
    "ship",
)


def skill_data_root() -> Path:
    """Return the directory containing all bundled skill subdirectories."""
    ref = importlib.resources.files(_PACKAGE) / _DATA_SUBDIR
    p = Path(str(ref))
    if not p.is_dir():
        raise RuntimeError(
            f"skill_data directory not found at {p!r}. "
            "Re-install the package to restore bundled skill data."
        )
    return p


def skill_dir(name: str) -> Path:
    """Return the root directory for a single bundled skill.

    Raises ``KeyError`` if *name* is not a bundled skill.
    Raises ``RuntimeError`` if the on-disk directory is missing.
    """
    if name not in SKILL_NAMES:
        raise KeyError(f"Unknown skill: {name!r}. Available: {SKILL_NAMES}")
    p = skill_data_root() / name
    if not p.is_dir():
        raise RuntimeError(f"Skill directory missing: {p!r}")
    return p
