"""Ruleset resolution and stable hashing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import orjson

from llm_sca_tooling.sarif.adapters.base import RulesetConfig

__all__ = ["ResolvedRuleset", "resolve_ruleset"]


@dataclass(frozen=True)
class ResolvedRuleset(RulesetConfig):
    ruleset_id: str = "ruleset:default"
    ruleset_name: str | None = None


def resolve_ruleset(
    entries: list[str] | None = None,
    *,
    offline: bool = True,
    base_dir: Path | None = None,
) -> ResolvedRuleset:
    raw_entries = entries or ["default"]
    resolved: list[str] = []
    for entry in raw_entries:
        path = (
            (base_dir / entry)
            if base_dir and not Path(entry).is_absolute()
            else Path(entry)
        )
        if path.exists():
            resolved.append(path.read_text())
        elif offline and entry.startswith("p/"):
            raise ValueError(f"ruleset {entry!r} requires network access")
        else:
            resolved.append(entry)
    digest = hashlib.sha256(
        orjson.dumps(resolved, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()[:16]
    return ResolvedRuleset(
        entries=raw_entries,
        offline=offline,
        ruleset_id=f"ruleset:{digest}",
        ruleset_name=",".join(raw_entries),
    )
