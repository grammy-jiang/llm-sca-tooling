"""Policy evaluator skeleton.

Evaluates whether a proposed tool call is allowed, denied, or requires
approval under the active permission profile.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm_sca_tooling.governance.permissions import PermissionProfileLoader
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["PolicyDecision", "PolicyEvaluator"]

logger = get_logger(__name__)

_LOADER = PermissionProfileLoader()


@dataclass(frozen=True)
class PolicyDecision:
    action: str  # allow | deny | approval_required | blocked
    reason: str
    policy_id: str = "agents-md-v0"


class PolicyEvaluator:
    """Evaluate tool-call events against a permission profile.

    Args:
        profile_loader: Loader for named permission profiles.
        path_allowlist: Additional path allowlist entries (overrides profile default).
        network_deny_by_default: Whether network egress is denied by default.
    """

    def __init__(
        self,
        profile_loader: PermissionProfileLoader | None = None,
        path_allowlist: list[str] | None = None,
        network_deny_by_default: bool = True,
    ) -> None:
        self._loader = profile_loader or _LOADER
        self._extra_paths = path_allowlist or []
        self._deny_network = network_deny_by_default

    def evaluate_tool_call(
        self,
        tool_name: str,
        tool_category: str,
        permission_profile: str,
        requested_path: str | None = None,
        network_required: bool = False,
    ) -> PolicyDecision:
        """Return an allow/deny/approval_required decision.

        Args:
            tool_name: Name of the tool being called.
            tool_category: One of read | search | edit | execute | review | commit.
            permission_profile: Active permission profile name.
            requested_path: File or directory path being accessed (for edit/execute).
            network_required: Whether the tool requires network access.
        """
        profile = self._loader.load(permission_profile)

        if network_required and self._deny_network and not profile.network_allowed:
            decision = PolicyDecision(
                action="deny",
                reason=f"Network egress denied for profile {permission_profile!r}",
            )
            logger.debug(
                "policy: %s %r → %s (%s)",
                tool_category,
                tool_name,
                decision.action,
                decision.reason,
            )
            return decision

        if tool_category not in profile.allowed_categories:
            if tool_category in profile.require_approval_for:
                decision = PolicyDecision(
                    action="approval_required",
                    reason=(
                        f"Category {tool_category!r} requires"
                        f" approval in {permission_profile!r}"
                    ),
                )
            else:
                decision = PolicyDecision(
                    action="deny",
                    reason=f"Category {tool_category!r} not allowed in {permission_profile!r}",  # noqa: E501
                )
            logger.debug(
                "policy: %s %r → %s", tool_category, tool_name, decision.action
            )
            return decision

        if requested_path is not None and tool_category in ("edit", "execute"):
            allowlist = list(profile.path_allowlist) + self._extra_paths
            if allowlist and not any(requested_path.startswith(p) for p in allowlist):
                decision = PolicyDecision(
                    action="deny",
                    reason=f"Path {requested_path!r} outside allowlist for {permission_profile!r}",  # noqa: E501
                )
                logger.debug(
                    "policy: %s %r → %s (path)",
                    tool_category,
                    tool_name,
                    decision.action,
                )
                return decision

        decision = PolicyDecision(action="allow", reason="within permitted scope")
        logger.debug("policy: %s %r → allow", tool_category, tool_name)
        return decision
