"""TypeScript module resolution (tsconfig paths + node_modules lookup)."""

from __future__ import annotations

import json
import re
from pathlib import Path


class TypeScriptModuleResolver:
    """Resolve TypeScript import paths to filesystem paths.

    Supports:
    - Relative imports (``./foo``, ``../bar``)
    - tsconfig ``paths`` mappings
    - ``node_modules`` package lookups
    """

    EXTENSIONS = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs")

    def __init__(
        self,
        repo_root: Path,
        tsconfig_paths: dict[str, list[str]] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self._paths: dict[str, list[str]] = tsconfig_paths or {}
        self._package_main_cache: dict[str, str | None] = {}

    @classmethod
    def from_tsconfig(cls, repo_root: Path) -> TypeScriptModuleResolver:
        """Build from tsconfig.json in repo_root (falls back to empty if missing)."""
        paths: dict[str, list[str]] = {}
        for name in ("tsconfig.json", "tsconfig.base.json"):
            candidate = repo_root / name
            if candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    paths = data.get("compilerOptions", {}).get("paths", {})
                except (json.JSONDecodeError, OSError):
                    pass
                break
        return cls(repo_root, tsconfig_paths=paths)

    def resolve(self, import_path: str, from_file: str | Path) -> str | None:
        """Return an absolute path string, or None if unresolvable."""
        from_dir = Path(from_file).parent
        if import_path.startswith("."):
            return self._resolve_relative(import_path, from_dir)
        resolved = self._resolve_paths_alias(import_path, from_dir)
        if resolved:
            return resolved
        return self._resolve_node_modules(import_path)

    # -- private helpers --

    def _resolve_relative(self, import_path: str, from_dir: Path) -> str | None:
        candidate = (from_dir / import_path).resolve()
        if candidate.is_file():
            return str(candidate)
        for ext in self.EXTENSIONS:
            with_ext = candidate.with_suffix(ext)
            if with_ext.is_file():
                return str(with_ext)
        for ext in self.EXTENSIONS:
            index = candidate / f"index{ext}"
            if index.is_file():
                return str(index)
        return None

    def _resolve_paths_alias(
        self, import_path: str, from_dir: Path
    ) -> str | None:  # noqa: ARG002
        for pattern, targets in self._paths.items():
            regex = re.escape(pattern).replace(r"\*", "(.*)")
            m = re.fullmatch(regex, import_path)
            if m:
                wildcard = m.group(1) if m.lastindex else ""
                for target in targets:
                    resolved_target = target.replace("*", wildcard)
                    candidate = (self.repo_root / resolved_target).resolve()
                    result = self._try_with_extensions(candidate)
                    if result:
                        return result
        return None

    def _resolve_node_modules(self, import_path: str) -> str | None:
        package_name = (
            import_path.split("/")[0]
            if not import_path.startswith("@")
            else "/".join(import_path.split("/")[:2])
        )
        nm = self.repo_root / "node_modules" / package_name
        if not nm.is_dir():
            return None
        if package_name in self._package_main_cache:
            return self._package_main_cache[package_name]
        pkg_json = nm / "package.json"
        if pkg_json.is_file():
            try:
                meta = json.loads(pkg_json.read_text(encoding="utf-8"))
                main = meta.get("types") or meta.get("typings") or meta.get("main")
                if main:
                    resolved = str((nm / main).resolve())
                    self._package_main_cache[package_name] = resolved
                    return resolved
            except (json.JSONDecodeError, OSError):
                pass
        self._package_main_cache[package_name] = None
        return None

    def _try_with_extensions(self, candidate: Path) -> str | None:
        if candidate.is_file():
            return str(candidate)
        for ext in self.EXTENSIONS:
            with_ext = candidate.with_suffix(ext)
            if with_ext.is_file():
                return str(with_ext)
        for ext in self.EXTENSIONS:
            index = candidate / f"index{ext}"
            if index.is_file():
                return str(index)
        return None
