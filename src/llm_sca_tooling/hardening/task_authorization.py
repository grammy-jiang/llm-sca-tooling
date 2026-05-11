"""Task TTL and authorization hardening.

Expired tasks are pruned on a configurable schedule.  Every task is bound
to the authorization context that created it; cross-context access is
denied.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["TaskAuthorizationHardener", "TaskRecord"]

logger = get_logger(__name__)

_DEFAULT_MAX_TTL = 86400  # 24 h


@dataclass
class TaskRecord:
    task_id: str
    workflow: str
    status: str  # pending | running | complete | expired
    created_at: str
    ttl_seconds: int
    authorization_context_hash: str
    result: Any | None = None
    expires_at: str = field(init=False)

    def __post_init__(self) -> None:
        created = datetime.fromisoformat(self.created_at)
        self.expires_at = (created + timedelta(seconds=self.ttl_seconds)).isoformat()

    def is_expired(self) -> bool:
        return datetime.now(UTC) > datetime.fromisoformat(self.expires_at)


class TaskAuthorizationHardener:
    """Store, retrieve, and prune tasks with TTL and auth-context enforcement.

    Args:
        max_ttl_seconds: Hard cap on task TTL (default 86400 s / 24 h).
    """

    def __init__(self, max_ttl_seconds: int = _DEFAULT_MAX_TTL) -> None:
        self._max_ttl = max_ttl_seconds
        self._tasks: dict[str, TaskRecord] = {}

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def create_task(
        self,
        workflow: str,
        ttl_seconds: int,
        auth_context: str,
    ) -> TaskRecord:
        """Create a task bound to *auth_context*.

        TTL is capped at ``max_ttl_seconds``.
        """
        effective_ttl = min(ttl_seconds, self._max_ttl)
        task = TaskRecord(
            task_id=f"task:{uuid.uuid4().hex[:12]}",
            workflow=workflow,
            status="pending",
            created_at=datetime.now(UTC).isoformat(),
            ttl_seconds=effective_ttl,
            authorization_context_hash=self._hash_context(auth_context),
        )
        self._tasks[task.task_id] = task
        logger.debug("created task %s ttl=%ds", task.task_id, effective_ttl)
        return task

    # ------------------------------------------------------------------
    # Task access
    # ------------------------------------------------------------------

    def get_task(self, task_id: str, auth_context: str) -> TaskRecord:
        """Return the task or raise ``PermissionError`` / ``KeyError``."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task.authorization_context_hash != self._hash_context(auth_context):
            raise PermissionError(f"Authorization context mismatch for task {task_id}")
        if task.is_expired():
            task.status = "expired"
        return task

    def complete_task(self, task_id: str, auth_context: str, result: Any) -> TaskRecord:
        """Mark a task complete and store its result."""
        task = self.get_task(task_id, auth_context)
        task.status = "complete"
        task.result = result
        return task

    # ------------------------------------------------------------------
    # TTL pruning
    # ------------------------------------------------------------------

    def prune_expired(self) -> list[str]:
        """Remove expired tasks from the store.

        Returns the list of pruned task IDs.
        """
        pruned: list[str] = []
        for task_id, task in list(self._tasks.items()):
            if task.is_expired():
                task.status = "expired"
                del self._tasks[task_id]
                pruned.append(task_id)
        if pruned:
            logger.info("Pruned %d expired tasks", len(pruned))
        return pruned

    def recover_after_restart(self) -> None:
        """Re-evaluate TTL on all tasks; immediately expire any that lapsed."""
        self.prune_expired()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_context(auth_context: str) -> str:
        return hashlib.sha256(auth_context.encode()).hexdigest()
