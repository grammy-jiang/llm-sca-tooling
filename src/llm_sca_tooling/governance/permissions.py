"""Permission profile loader and built-in profile definitions."""

from __future__ import annotations

from dataclasses import dataclass

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["PermissionProfile", "PermissionProfileLoader"]

logger = get_logger(__name__)

_ALL_CATEGORIES = ["read", "search", "edit", "execute", "review", "commit"]


@dataclass(frozen=True)
class PermissionProfile:
    name: str
    allowed_categories: list[str]
    path_allowlist: list[str]
    network_allowed: bool
    require_approval_for: list[str]


_BUILT_IN: dict[str, PermissionProfile] = {
    "read-only": PermissionProfile(
        name="read-only",
        allowed_categories=["read", "search"],
        path_allowlist=[],
        network_allowed=False,
        require_approval_for=["edit", "execute", "review", "commit"],
    ),
    "plan": PermissionProfile(
        name="plan",
        allowed_categories=["read", "search", "edit"],
        path_allowlist=[".agent/plan.md"],
        network_allowed=False,
        require_approval_for=["execute", "review", "commit"],
    ),
    "scoped-edit": PermissionProfile(
        name="scoped-edit",
        allowed_categories=["read", "search", "edit"],
        path_allowlist=[],
        network_allowed=False,
        require_approval_for=["execute", "review", "commit"],
    ),
    "scoped-execute": PermissionProfile(
        name="scoped-execute",
        allowed_categories=["read", "search", "edit", "execute"],
        path_allowlist=[],
        network_allowed=False,
        require_approval_for=["review", "commit"],
    ),
    "review-commit": PermissionProfile(
        name="review-commit",
        allowed_categories=_ALL_CATEGORIES,
        path_allowlist=[],
        network_allowed=False,
        require_approval_for=[],
    ),
}


class PermissionProfileLoader:
    """Load named permission profiles.

    Built-in profiles cover all five standard modes. Custom profiles can be
    registered via :meth:`register`.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PermissionProfile] = dict(_BUILT_IN)

    def load(self, profile_name: str) -> PermissionProfile:
        """Return the profile for *profile_name*.

        Raises:
            KeyError: If the profile is not found.
        """
        try:
            return self._profiles[profile_name]
        except KeyError:
            available = sorted(self._profiles)
            msg = (
                f"Permission profile {profile_name!r} not found. Available: {available}"
            )
            raise KeyError(msg) from None

    def list_profiles(self) -> list[str]:
        """Return the names of all available profiles."""
        return sorted(self._profiles)

    def register(self, profile: PermissionProfile) -> None:
        """Register a custom profile, overriding any with the same name."""
        self._profiles[profile.name] = profile
        logger.debug("Registered permission profile %r", profile.name)
