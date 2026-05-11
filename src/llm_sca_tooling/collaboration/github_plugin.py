"""GitHub collaboration plugin stub (Gap 3)."""

from __future__ import annotations

from llm_sca_tooling.collaboration.base import CollaborationPlugin, ReviewComment


class GitHubPlugin(CollaborationPlugin):
    """GitHub collaboration plugin. Requires GITHUB_TOKEN env var."""

    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.token = token

    def post_review_comments(self, comments: list[ReviewComment], pr_id: str) -> None:
        """Post review comments via the GitHub API (not yet implemented)."""
        raise NotImplementedError("GitHub API integration not yet implemented")

    def create_issue(self, title: str, body: str) -> str:
        """Create a GitHub issue (not yet implemented)."""
        raise NotImplementedError("GitHub API integration not yet implemented")
