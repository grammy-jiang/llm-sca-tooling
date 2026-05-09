"""package.json metadata and script extraction."""

from __future__ import annotations

import json
from pathlib import Path


class PackageMetadata:
    def parse(self, repo_root: Path) -> dict:
        path = repo_root / "package.json"
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "name": payload.get("name"),
            "version": payload.get("version"),
            "scripts": payload.get("scripts", {}),
            "dependencies": payload.get("dependencies", {}),
            "devDependencies": payload.get("devDependencies", {}),
            "workspaces": payload.get("workspaces"),
            "test_frameworks": [
                name
                for name in ("jest", "vitest", "mocha")
                if name in payload or name in payload.get("devDependencies", {})
            ],
        }
