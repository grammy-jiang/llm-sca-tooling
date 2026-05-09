"""Ruleset resolution for offline analyser execution."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.sarif.adapters.base import ResolvedRuleset
from llm_sca_tooling.storage.ids import stable_hash


def resolve_ruleset(ruleset: str | list[str] | dict | None, *, repo_root: Path, offline: bool = True) -> ResolvedRuleset:
    if ruleset is None:
        return ResolvedRuleset(ruleset_id="ruleset:default", ruleset_name="default", args=[])
    items = ruleset if isinstance(ruleset, list) else [ruleset]
    args: list[str] = []
    diagnostics: list[str] = []
    canonical_items = []
    for item in items:
        if isinstance(item, dict):
            canonical_items.append(item)
            continue
        text = str(item)
        candidate = (repo_root / text).resolve() if not Path(text).is_absolute() else Path(text)
        if candidate.exists():
            args.extend(["--config", str(candidate)])
            canonical_items.append({"path": candidate.read_text(encoding="utf-8")})
        elif offline and (text.startswith("p/") or text.startswith("r/")):
            diagnostics.append(f"NETWORK_REQUIRED:{text}")
        else:
            args.extend(["--config", text])
            canonical_items.append(text)
    return ResolvedRuleset(ruleset_id=f"ruleset:{stable_hash(canonical_json(canonical_items), length=16)}", ruleset_name="custom", args=args, diagnostics=diagnostics)

