"""Smoke tests: package is importable and basic invariants hold."""

from __future__ import annotations

import importlib
import importlib.metadata


def test_package_importable() -> None:
    import llm_sca_tooling

    assert hasattr(llm_sca_tooling, "__version__")


def test_version_is_string() -> None:
    from llm_sca_tooling import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_fallback_when_package_metadata_missing(monkeypatch) -> None:
    import llm_sca_tooling

    def missing_version(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    with monkeypatch.context() as patch:
        patch.setattr(importlib.metadata, "version", missing_version)
        module = importlib.reload(llm_sca_tooling)
        assert module.__version__ == "0.0.0.dev0"

    importlib.reload(llm_sca_tooling)


def test_all_skeleton_modules_importable() -> None:
    modules = [
        "llm_sca_tooling.errors",
        "llm_sca_tooling.config",
        "llm_sca_tooling.telemetry",
        "llm_sca_tooling.telemetry.logging",
        "llm_sca_tooling.telemetry.trace_writer",
        "llm_sca_tooling.operations",
        "llm_sca_tooling.operations.budget",
        "llm_sca_tooling.operations.run_records",
        "llm_sca_tooling.governance",
        "llm_sca_tooling.governance.permissions",
        "llm_sca_tooling.governance.policy",
        "llm_sca_tooling.plugins",
        "llm_sca_tooling.plugins.registry",
        "llm_sca_tooling.harness",
        "llm_sca_tooling.harness.condition",
        "llm_sca_tooling.schemas",
        "llm_sca_tooling.graph",
        "llm_sca_tooling.indexing",
        "llm_sca_tooling.sarif",
        "llm_sca_tooling.workflows",
        "llm_sca_tooling.evaluation",
        "llm_sca_tooling.memory",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"Failed to import {mod_name}"


def test_cli_app_importable() -> None:
    from llm_sca_tooling.cli.main import app

    assert app is not None
