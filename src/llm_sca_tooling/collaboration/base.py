"""Collaboration plugin ABCs for posting review comments and issues (Gap 3)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.schemas.base import StrictBaseModel


class ReviewComment(StrictBaseModel):
    """A single review comment attached to a file location."""

    file_path: str
    line: int | None = None
    body: str
    severity: str = "info"


class CollaborationPlugin(ABC):
    """Base class for code review collaboration plugins."""

    @abstractmethod
    def post_review_comments(self, comments: list[ReviewComment], pr_id: str) -> None:
        """Post *comments* to the pull request identified by *pr_id*."""
        ...

    @abstractmethod
    def create_issue(self, title: str, body: str) -> str:
        """Create an issue with *title* and *body*; return the issue URL/id."""
        ...
