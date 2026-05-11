"""Tests for TaskAuthorizationHardener."""

from __future__ import annotations

import pytest

from llm_sca_tooling.hardening.task_authorization import TaskAuthorizationHardener


def test_create_and_get_same_context() -> None:
    h = TaskAuthorizationHardener()
    task = h.create_task("workflow1", ttl_seconds=3600, auth_context="ctx-abc")
    retrieved = h.get_task(task.task_id, "ctx-abc")
    assert retrieved.task_id == task.task_id


def test_get_wrong_context_raises_permission_error() -> None:
    h = TaskAuthorizationHardener()
    task = h.create_task("workflow1", ttl_seconds=3600, auth_context="ctx-abc")
    with pytest.raises(PermissionError):
        h.get_task(task.task_id, "ctx-xyz")


def test_get_unknown_task_raises_key_error() -> None:
    h = TaskAuthorizationHardener()
    with pytest.raises(KeyError):
        h.get_task("task:doesnotexist", "ctx-abc")


def test_complete_task_updates_status() -> None:
    h = TaskAuthorizationHardener()
    task = h.create_task("workflow1", ttl_seconds=3600, auth_context="ctx-abc")
    completed = h.complete_task(task.task_id, "ctx-abc", result={"ok": True})
    assert completed.status == "complete"


def test_ttl_capped_at_max() -> None:
    h = TaskAuthorizationHardener(max_ttl_seconds=60)
    task = h.create_task("workflow1", ttl_seconds=9999, auth_context="ctx-abc")
    assert task.ttl_seconds == 60


def test_prune_expired_removes_lapsed_tasks() -> None:
    h = TaskAuthorizationHardener()
    task = h.create_task("workflow1", ttl_seconds=0, auth_context="ctx-abc")
    pruned = h.prune_expired()
    assert task.task_id in pruned
