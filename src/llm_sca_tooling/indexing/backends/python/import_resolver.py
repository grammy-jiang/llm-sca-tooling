"""Small Python import resolver helpers."""

from __future__ import annotations


class ImportResolver:
    def module_to_path_candidates(self, module_name: str) -> list[str]:
        base = module_name.replace(".", "/")
        return [
            f"{base}.py",
            f"{base}/__init__.py",
            f"src/{base}.py",
            f"src/{base}/__init__.py",
        ]
