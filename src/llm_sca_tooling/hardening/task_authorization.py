"""Task TTL and authorization hardening."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class TaskAuthorizationHardener:
    def __init__(self, *, max_task_ttl_seconds: int = 86_400) -> None:
        self.max_task_ttl_seconds = max_task_ttl_seconds

    def clamp_ttl(self, ttl_seconds: int) -> int:
        return min(ttl_seconds, self.max_task_ttl_seconds)

    def can_access(
        self,
        *,
        task_auth_hash: str | None,
        request_auth_hash: str | None,
        single_user: bool,
    ) -> bool:
        return single_user or task_auth_hash == request_auth_hash

    def expired(self, *, created_ts: str, ttl_seconds: int) -> bool:
        created = datetime.fromisoformat(created_ts.replace("Z", "+00:00"))
        return datetime.now(UTC) > created + timedelta(
            seconds=self.clamp_ttl(ttl_seconds)
        )
