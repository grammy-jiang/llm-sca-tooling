"""CTest and CMake test evidence detection."""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["detect_ctest_commands"]


def detect_ctest_commands(repo_root: Path) -> list[str]:
    commands: set[str] = set()
    cmake = repo_root / "CMakeLists.txt"
    if cmake.exists():
        text = cmake.read_text(errors="replace")
        if "enable_testing" in text or "add_test" in text:
            commands.add("ctest")
        commands.update(
            f"cmake-target:{name}"
            for name in re.findall(r"add_executable\((\w+)", text)
        )
    for path in repo_root.rglob("CTestTestfile.cmake"):
        commands.add(str(path.relative_to(repo_root)).replace("\\", "/"))
    return sorted(commands)
