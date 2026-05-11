"""Typed permission profile set for workspace-wide permission management.

Phase 19 hardens all six permission modes and introduces ``PermissionProfileSet``
as the typed aggregate that controls per-repo and per-workflow overrides.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["PermissionMode", "PermissionProfileDef", "PermissionProfileSet"]

logger = get_logger(__name__)

PermissionMode = Literal[
    "read_only",
    "read_search",
    "read_search_edit",
    "read_search_execute",
    "review",
    "commit",
]

_MODE_CAPABILITIES: dict[PermissionMode, dict[str, bool]] = {
    "read_only": {
        "read": True,
        "search": False,
        "edit": False,
        "execute": False,
        "review": False,
        "commit": False,
    },
    "read_search": {
        "read": True,
        "search": True,
        "edit": False,
        "execute": False,
        "review": False,
        "commit": False,
    },
    "read_search_edit": {
        "read": True,
        "search": True,
        "edit": True,
        "execute": False,
        "review": False,
        "commit": False,
    },
    "read_search_execute": {
        "read": True,
        "search": True,
        "edit": False,
        "execute": True,
        "review": False,
        "commit": False,
    },
    "review": {
        "read": True,
        "search": True,
        "edit": False,
        "execute": False,
        "review": True,
        "commit": False,
    },
    "commit": {
        "read": True,
        "search": True,
        "edit": True,
        "execute": True,
        "review": True,
        "commit": True,
    },
}

# Default (most permissive) mode used when checking widening.
_DEFAULT_MODE: PermissionMode = "read_only"


class PermissionProfileDef(BaseModel):
    """One permission mode definition with its capability matrix."""

    model_config = ConfigDict(extra="forbid")

    mode: PermissionMode
    read: bool
    search: bool
    edit: bool
    execute: bool
    review: bool
    commit: bool

    @classmethod
    def for_mode(cls, mode: PermissionMode) -> PermissionProfileDef:
        caps = _MODE_CAPABILITIES[mode]
        return cls(mode=mode, **caps)

    def allows(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))


class NetworkPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_destinations: list[str] = []
    deny_by_default: bool = True


class PermissionProfileSet(BaseModel):
    """Workspace-wide permission profile set.

    Controls the active permission mode plus optional per-repo and
    per-workflow overrides.  A mode that is wider than the workspace
    default is flagged as a ``relaxed`` drift finding.
    """

    model_config = ConfigDict(extra="forbid")

    default_mode: PermissionMode = "read_only"
    per_repo_overrides: dict[str, PermissionMode] = {}
    per_workflow_overrides: dict[str, PermissionMode] = {}
    network_policy: NetworkPolicy = NetworkPolicy()
    path_allowlist: list[str] = []
    execute_allowlist: list[str] = []
    review_allowlist: list[str] = []
    commit_allowlist: list[str] = []

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def effective_mode(
        self,
        repo_id: str | None = None,
        workflow: str | None = None,
    ) -> PermissionMode:
        """Return the effective mode for the given context."""
        if workflow and workflow in self.per_workflow_overrides:
            return self.per_workflow_overrides[workflow]
        if repo_id and repo_id in self.per_repo_overrides:
            return self.per_repo_overrides[repo_id]
        return self.default_mode

    def allows(
        self,
        capability: str,
        repo_id: str | None = None,
        workflow: str | None = None,
    ) -> bool:
        mode = self.effective_mode(repo_id, workflow)
        return _MODE_CAPABILITIES.get(mode, {}).get(capability, False)

    def profile(self, mode: PermissionMode | None = None) -> PermissionProfileDef:
        """Return the ``PermissionProfileDef`` for *mode* (default: default_mode)."""
        return PermissionProfileDef.for_mode(mode or self.default_mode)

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def is_widened(
        self,
        mode: PermissionMode,
        baseline: PermissionMode = _DEFAULT_MODE,
    ) -> bool:
        """Return ``True`` if *mode* grants more capabilities than *baseline*."""
        baseline_caps = _MODE_CAPABILITIES[baseline]
        mode_caps = _MODE_CAPABILITIES[mode]
        return any(
            mode_caps.get(cap, False) and not baseline_caps.get(cap, False)
            for cap in ("search", "edit", "execute", "review", "commit")
        )
