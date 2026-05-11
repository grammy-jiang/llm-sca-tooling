"""Tests for PermissionProfileSet."""

from __future__ import annotations

from llm_sca_tooling.hardening.permission_profiles import (
    PermissionProfileDef,
    PermissionProfileSet,
)


def test_read_only_is_not_widened() -> None:
    pps = PermissionProfileSet()
    assert not pps.is_widened("read_only")


def test_read_search_edit_is_widened() -> None:
    pps = PermissionProfileSet()
    assert pps.is_widened("read_search_edit")


def test_commit_is_widened() -> None:
    pps = PermissionProfileSet()
    assert pps.is_widened("commit")


def test_effective_mode_returns_default() -> None:
    pps = PermissionProfileSet()
    assert pps.effective_mode() == "read_only"


def test_per_repo_override_takes_effect() -> None:
    pps = PermissionProfileSet(per_repo_overrides={"repo1": "read_search_edit"})
    assert pps.effective_mode(repo_id="repo1") == "read_search_edit"


def test_for_mode_returns_correct_profile() -> None:
    profile = PermissionProfileDef.for_mode("read_only")
    assert not profile.edit
    assert not profile.execute


def test_read_search_edit_profile_allows_edit() -> None:
    profile = PermissionProfileDef.for_mode("read_search_edit")
    assert profile.edit
