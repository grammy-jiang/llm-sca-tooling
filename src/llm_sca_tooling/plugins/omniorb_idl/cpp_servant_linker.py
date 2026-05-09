"""C++ servant heuristics for IDL interfaces."""

from __future__ import annotations

import re
from pathlib import Path


def find_cpp_servants(repo_root: Path, interface_name: str) -> list[dict]:
    servants = []
    patterns = [f"POA_{interface_name}", f"{interface_name}Servant", f"{interface_name}_i"]
    for path in list(repo_root.rglob("*.cc")) + list(repo_root.rglob("*.cpp")) + list(repo_root.rglob("*.h")) + list(repo_root.rglob("*.hpp")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern in text:
                match = re.search(rf"\bclass\s+([A-Za-z_][\w]*)[^{{;]*{re.escape(pattern)}", text) or re.search(rf"\bclass\s+({re.escape(pattern)})\b", text)
                servants.append({"file_path": path.relative_to(repo_root).as_posix(), "class_name": match.group(1) if match else pattern, "line": text[: text.find(pattern)].count("\n") + 1})
                break
    return servants
