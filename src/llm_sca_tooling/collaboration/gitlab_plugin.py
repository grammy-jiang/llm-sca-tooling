"""GitLab collaboration plugin stub (Gap 3)."""

from __future__ import annotations

from llm_sca_tooling.collaboration.base import CollaborationPlugin, ReviewComment


class GitLabPlugin(CollaborationPlugin):
    """GitLab collaboration plugin. Requires GITLAB_TOKEN env var."""

    def __init__(self, project_id: str, token: str | None = None) -> None:
        self.project_id = project_id
        self.token = token

    def post_review_comments(self, comments: list[ReviewComment], pr_id: str) -> None:
        """Post review comments via the GitLab API (not yet implemented)."""
        raise NotImplementedError("GitLab API integration not yet implemented")

    def create_issue(self, title: str, body: str) -> str:
        """Create a GitLab issue (not yet implemented)."""
        raise NotImplementedError("GitLab API integration not yet implemented")
