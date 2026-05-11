"""Heuristic JS/TS test runner detection."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.typescript.package_meta import PackageMetadata

__all__ = ["detect_test_runners"]


def detect_test_runners(repo_root: Path, package: PackageMetadata) -> list[str]:
    runners: set[str] = set()
    test_script = package.scripts.get("test", "")
    for name in ("jest", "vitest", "mocha", "karma", "jasmine"):
        if name in test_script or (repo_root / f"{name}.config.js").exists():
            runners.add(name)
    for pattern, name in [
        ("jest.config.*", "jest"),
        ("vitest.config.*", "vitest"),
        (".mocharc.*", "mocha"),
        ("karma.conf.*", "karma"),
    ]:
        if any(repo_root.glob(pattern)):
            runners.add(name)
    if (repo_root / "jasmine.json").exists() or (
        repo_root / "spec" / "support" / "jasmine.json"
    ).exists():
        runners.add("jasmine")
    return sorted(runners)
