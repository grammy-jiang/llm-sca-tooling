"""JavaScript/TypeScript test-runner detection."""

from __future__ import annotations

from pathlib import Path


def detect_ts_test_runners(repo_root: Path, package_meta: dict) -> list[dict]:
    runners: list[dict] = []
    scripts = package_meta.get("scripts", {})
    test_script = scripts.get("test")
    if test_script:
        runners.append(
            {
                "runner": _runner_from_text(test_script),
                "source": "package.json:scripts.test",
                "command": test_script,
            }
        )
    for pattern, runner in (
        ("jest.config", "jest"),
        ("vitest.config", "vitest"),
        (".mocharc", "mocha"),
        ("karma.conf", "karma"),
    ):
        if any(path.name.startswith(pattern) for path in repo_root.iterdir()):
            runners.append({"runner": runner, "source": pattern})
    return runners


def _runner_from_text(value: str) -> str:
    lowered = value.lower()
    for runner in ("vitest", "jest", "mocha", "karma", "jasmine"):
        if runner in lowered:
            return runner
    return "npm-test"
