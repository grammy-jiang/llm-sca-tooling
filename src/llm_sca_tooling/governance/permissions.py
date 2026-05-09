"""Permission profile skeletons for tool policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionProfile:
    name: str
    allowed_categories: list[str]
    path_allowlist: list[str]
    network_allowed: bool
    require_approval_for: list[str]


DEFAULT_PATH_ALLOWLIST = [
    "src/",
    "tests/",
    "schemas/",
    "docs/",
    ".agent/",
    "AGENTS.md",
    "CLAUDE.md",
    "pyproject.toml",
    "tox.ini",
    "Makefile",
]


class PermissionProfileLoader:
    def __init__(self, path_allowlist: list[str] | None = None) -> None:
        self.path_allowlist = list(path_allowlist or DEFAULT_PATH_ALLOWLIST)

    def load(self, profile_name: str) -> PermissionProfile:
        profiles = self._profiles()
        if profile_name not in profiles:
            raise ValueError(f"unknown permission profile: {profile_name}")
        return profiles[profile_name]

    def list_profiles(self) -> list[str]:
        return list(self._profiles())

    def _profiles(self) -> dict[str, PermissionProfile]:
        return {
            "read-only": PermissionProfile(
                "read-only", ["read", "search"], [], False, []
            ),
            "plan": PermissionProfile(
                "plan", ["read", "search", "edit"], [".agent/plan.md"], False, []
            ),
            "scoped-edit": PermissionProfile(
                "scoped-edit",
                ["read", "search", "edit"],
                self.path_allowlist,
                False,
                [],
            ),
            "scoped-execute": PermissionProfile(
                "scoped-execute",
                ["read", "search", "edit", "execute"],
                self.path_allowlist,
                False,
                [],
            ),
            "review-commit": PermissionProfile(
                "review-commit",
                ["read", "search", "edit", "execute", "review", "commit"],
                self.path_allowlist,
                False,
                ["commit"],
            ),
        }
