"""Python IDL caller heuristics."""

from __future__ import annotations

import re
from pathlib import Path


def find_python_callers(repo_root: Path, stub_modules: list[str], method_names: list[str]) -> list[dict]:
    callers = []
    for path in repo_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        imports_stub = any(module in text for module in stub_modules)
        if not imports_stub:
            continue
        for method in method_names:
            match = re.search(rf"\.{re.escape(method)}\s*\(", text)
            if match:
                callers.append({"file_path": path.relative_to(repo_root).as_posix(), "function": f"call:{method}", "method": method, "line": text.count("\n", 0, match.start()) + 1})
    return callers
