"""Memory opt-in policy enforcement."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import now_ts
from llm_sca_tooling.memory.models import MemoryOptInPolicy


class MemoryDisabledError(Exception):
    """Raised when memory is disabled for the workspace or repo."""


def make_default_policy(workspace_id: str) -> MemoryOptInPolicy:
    return MemoryOptInPolicy(workspace_id=workspace_id)


def opt_in(policy: MemoryOptInPolicy, *, actor: str) -> MemoryOptInPolicy:
    return policy.model_copy(
        update={
            "enabled": True,
            "opt_in_ts": now_ts(),
            "opt_in_actor": actor,
        }
    )


def check_memory_enabled(policy: MemoryOptInPolicy, repo_id: str | None = None) -> None:
    if not policy.enabled:
        raise MemoryDisabledError("memory is disabled for this workspace")
    if repo_id and policy.per_repo_overrides.get(repo_id) is False:
        raise MemoryDisabledError(f"memory is disabled for repo {repo_id!r}")
