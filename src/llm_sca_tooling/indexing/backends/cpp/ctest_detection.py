"""CTest evidence detection."""

from __future__ import annotations

import re
from pathlib import Path


def detect_ctest(repo_root: Path) -> list[dict]:
    results = []
    cmake = repo_root / "CMakeLists.txt"
    if cmake.exists():
        text = cmake.read_text(encoding="utf-8")
        if "enable_testing" in text:
            results.append({"kind": "ctest_enabled", "source": "CMakeLists.txt"})
        for match in re.finditer(r"\badd_test\s*\(\s*(?:NAME\s+)?([A-Za-z_][\w.-]*)", text):
            results.append({"kind": "ctest_test", "name": match.group(1), "source": "CMakeLists.txt"})
    for testfile in repo_root.rglob("CTestTestfile.cmake"):
        results.append({"kind": "ctest_file", "source": testfile.relative_to(repo_root).as_posix()})
    return results
