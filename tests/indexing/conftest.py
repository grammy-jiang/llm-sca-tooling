"""Shared fixtures for indexing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.storage import WorkspaceStore

PYTHON_BASIC = (
    Path(__file__).parent.parent.parent / "fixtures" / "repos" / "python_basic"
)


@pytest.fixture()
async def workspace(tmp_path: Path) -> WorkspaceStore:
    return await WorkspaceStore.initialize(tmp_path, in_memory=True)


@pytest.fixture()
def indexing_config() -> IndexingConfig:
    return IndexingConfig(backend_timeout_ms=10_000)


@pytest.fixture()
def python_basic_repo() -> Path:
    return PYTHON_BASIC
