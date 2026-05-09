"""CMake build evidence parser."""

from __future__ import annotations

import re
from pathlib import Path


class CMakeBackend:
    def detect_targets(self, repo_root: Path) -> list[dict]:
        path = repo_root / "CMakeLists.txt"
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        targets = []
        for match in re.finditer(r"\b(add_executable|add_library)\s*\(\s*([A-Za-z_][\w.-]*)", text):
            targets.append({"kind": match.group(1), "name": match.group(2), "source": "CMakeLists.txt"})
        return targets
