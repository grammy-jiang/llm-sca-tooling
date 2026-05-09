"""Generated omniIDL artifact detection."""

from __future__ import annotations

from pathlib import Path


def generated_artifacts(repo_root: Path, interface_name: str) -> list[str]:
    matches = []
    lowered = interface_name.lower()
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith(("sk.cc", "_skel.cc", "_idl.py")) or (
            lowered in name and ("sk" in name or "idl" in name)
        ):
            matches.append(path.relative_to(repo_root).as_posix())
    return sorted(set(matches))
