"""Deterministic policy evaluator skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from llm_sca_tooling.governance.permissions import PermissionProfileLoader
from llm_sca_tooling.telemetry.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason: str
    policy_id: str


class PolicyEvaluator:
    def __init__(
        self,
        *,
        policy_id: str = "phase0-default",
        network_deny_by_default: bool = True,
        path_allowlist: list[str] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.network_deny_by_default = network_deny_by_default
        self.loader = PermissionProfileLoader(path_allowlist)

    def evaluate_tool_call(
        self,
        tool_name: str,
        tool_category: str,
        permission_profile: str,
        requested_path: str | None = None,
        network_required: bool = False,
    ) -> PolicyDecision:
        profile = self.loader.load(permission_profile)
        if (
            network_required
            and self.network_deny_by_default
            and not profile.network_allowed
        ):
            return self._decision(
                "deny", tool_name, "network egress is denied by default"
            )
        if (
            tool_category in {"execute", "commit"}
            and tool_category not in profile.allowed_categories
        ):
            return self._decision(
                "approval_required",
                tool_name,
                f"{tool_category} requires elevated permission profile",
            )
        if tool_category not in profile.allowed_categories:
            return self._decision(
                "deny",
                tool_name,
                f"category {tool_category} is not allowed in {profile.name}",
            )
        if (
            requested_path is not None
            and tool_category in {"edit", "execute", "commit"}
            and not _path_allowed(requested_path, profile.path_allowlist)
        ):
            return self._decision(
                "deny", tool_name, f"path is outside allowlist for {profile.name}"
            )
        if tool_category in profile.require_approval_for:
            return self._decision(
                "approval_required", tool_name, f"{tool_category} requires approval"
            )
        return self._decision("allow", tool_name, "allowed by permission profile")

    def _decision(self, action: str, tool_name: str, reason: str) -> PolicyDecision:
        decision = PolicyDecision(
            action=action, reason=reason, policy_id=self.policy_id
        )
        LOGGER.debug("Policy decision for %s: %s (%s)", tool_name, action, reason)
        return decision


def _path_allowed(path: str, allowlist: list[str]) -> bool:
    normalized = PurePosixPath(path).as_posix()
    for allowed in allowlist:
        allowed_normalized = PurePosixPath(allowed).as_posix()
        if allowed_normalized.endswith("/") and normalized.startswith(
            allowed_normalized
        ):
            return True
        if normalized == allowed_normalized:
            return True
    return False
