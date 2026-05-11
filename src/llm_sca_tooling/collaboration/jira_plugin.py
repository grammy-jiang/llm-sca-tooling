"""Jira collaboration plugin stub (Gap 3)."""

from __future__ import annotations

from llm_sca_tooling.collaboration.base import CollaborationPlugin, ReviewComment


class JiraPlugin(CollaborationPlugin):
    """Jira collaboration plugin. Requires JIRA_TOKEN and JIRA_URL env vars."""

    def __init__(self, project_key: str, token: str | None = None) -> None:
        self.project_key = project_key
        self.token = token

    def post_review_comments(self, comments: list[ReviewComment], pr_id: str) -> None:
        """Post review comments as a Jira comment (not yet implemented)."""
        raise NotImplementedError("Jira API integration not yet implemented")

    def create_issue(self, title: str, body: str) -> str:
        """Create a Jira issue (not yet implemented)."""
        raise NotImplementedError("Jira API integration not yet implemented")
