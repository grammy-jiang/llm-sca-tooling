"""Python stub heuristics for IDL interfaces."""

from __future__ import annotations

from pathlib import Path


def find_python_stubs(repo_root: Path, interface_name: str) -> list[dict]:
    stubs = []
    lowered = interface_name.lower()
    for path in repo_root.rglob("*.py"):
        name = path.name.lower()
        if (
            name.endswith("_idl.py")
            or "corba" in name
            or lowered in name
            and "idl" in name
        ):
            stubs.append(
                {
                    "file_path": path.relative_to(repo_root).as_posix(),
                    "module_name": path.stem,
                    "line": 1,
                }
            )
    return stubs
