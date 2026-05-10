"""Six hardened permission profiles."""

from __future__ import annotations

from llm_sca_tooling.hardening.models import (
    HardenedPermissionMode,
    PermissionProfile,
    PermissionProfileSet,
)

CAPABILITIES = {"read", "search", "edit", "execute", "review", "commit"}


def default_permission_profiles() -> dict[HardenedPermissionMode, PermissionProfile]:
    return {
        HardenedPermissionMode.READ_ONLY: PermissionProfile(
            mode=HardenedPermissionMode.READ_ONLY, read=True
        ),
        HardenedPermissionMode.READ_SEARCH: PermissionProfile(
            mode=HardenedPermissionMode.READ_SEARCH, read=True, search=True
        ),
        HardenedPermissionMode.READ_SEARCH_EDIT: PermissionProfile(
            mode=HardenedPermissionMode.READ_SEARCH_EDIT,
            read=True,
            search=True,
            edit=True,
        ),
        HardenedPermissionMode.READ_SEARCH_EXECUTE: PermissionProfile(
            mode=HardenedPermissionMode.READ_SEARCH_EXECUTE,
            read=True,
            search=True,
            execute=True,
        ),
        HardenedPermissionMode.REVIEW: PermissionProfile(
            mode=HardenedPermissionMode.REVIEW, read=True, search=True, review=True
        ),
        HardenedPermissionMode.COMMIT: PermissionProfile(
            mode=HardenedPermissionMode.COMMIT,
            read=True,
            search=True,
            edit=True,
            execute=True,
            review=True,
            commit=True,
        ),
    }


def resolve_permission_profile(
    profile_set: PermissionProfileSet,
    *,
    repo_id: str | None = None,
    workflow: str | None = None,
) -> PermissionProfile:
    """Resolve repo/workflow overrides into one of the six hardened profiles."""

    mode = profile_set.default_mode
    if workflow and workflow in profile_set.per_workflow_overrides:
        mode = profile_set.per_workflow_overrides[workflow]
    if repo_id and repo_id in profile_set.per_repo_overrides:
        mode = profile_set.per_repo_overrides[repo_id]
    return default_permission_profiles()[mode]


def permission_allows(
    profile: PermissionProfile | HardenedPermissionMode,
    capability: str,
) -> bool:
    """Return whether a hardened profile allows a primitive capability."""

    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability: {capability}")
    resolved = (
        default_permission_profiles()[profile]
        if isinstance(profile, HardenedPermissionMode)
        else profile
    )
    return bool(getattr(resolved, capability))
