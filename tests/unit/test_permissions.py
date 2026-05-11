"""Tests for the permission profile loader."""

from __future__ import annotations

import pytest

from llm_sca_tooling.governance.permissions import (
    PermissionProfile,
    PermissionProfileLoader,
)


@pytest.fixture()
def loader() -> PermissionProfileLoader:
    return PermissionProfileLoader()


def test_all_built_in_profiles_loadable(loader: PermissionProfileLoader) -> None:
    for name in ("read-only", "plan", "scoped-edit", "scoped-execute", "review-commit"):
        profile = loader.load(name)
        assert profile.name == name


def test_list_profiles_includes_built_ins(loader: PermissionProfileLoader) -> None:
    names = loader.list_profiles()
    assert "read-only" in names
    assert "review-commit" in names


def test_unknown_profile_raises_key_error(loader: PermissionProfileLoader) -> None:
    with pytest.raises(KeyError):
        loader.load("superadmin")


def test_register_custom_profile(loader: PermissionProfileLoader) -> None:
    custom = PermissionProfile(
        name="custom",
        allowed_categories=["read"],
        path_allowlist=[],
        network_allowed=False,
        require_approval_for=[],
    )
    loader.register(custom)
    assert loader.load("custom") is custom


def test_read_only_allows_only_read_and_search(loader: PermissionProfileLoader) -> None:
    profile = loader.load("read-only")
    assert "read" in profile.allowed_categories
    assert "search" in profile.allowed_categories
    assert "edit" not in profile.allowed_categories


def test_review_commit_allows_all_categories(loader: PermissionProfileLoader) -> None:
    profile = loader.load("review-commit")
    for cat in ("read", "search", "edit", "execute", "review", "commit"):
        assert cat in profile.allowed_categories
