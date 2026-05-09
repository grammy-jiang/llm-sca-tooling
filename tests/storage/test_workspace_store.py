from __future__ import annotations

from llm_sca_tooling.storage import initialize_workspace, open_workspace
from llm_sca_tooling.storage.migrations import STORAGE_VERSION


def test_workspace_initializes_and_reopens(tmp_path) -> None:
    store = initialize_workspace(tmp_path / ".llm-sca")
    status = store.workspace_status()
    store.close()
    reopened = open_workspace(tmp_path / ".llm-sca")
    assert reopened.workspace_status().workspace_id == status.workspace_id
    assert reopened.workspace_status().storage_version == STORAGE_VERSION
    reopened.close()


def test_workspace_status_reports_schema_versions(workspace) -> None:
    status = workspace.workspace_status()
    assert status.schema_versions["phase1"] == "0.1.0"
    assert status.last_migration == "0002"
