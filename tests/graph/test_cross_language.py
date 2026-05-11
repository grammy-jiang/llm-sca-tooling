"""Tests for the LanguagePlugin ABC and companion dataclasses (Gap 6)."""

from __future__ import annotations

import pytest


def test_language_plugin_abc_has_required_methods() -> None:
    """LanguagePlugin must declare all three extraction abstract methods."""
    from llm_sca_tooling.graph.plugins.base import LanguagePlugin

    assert hasattr(LanguagePlugin, "extract_symbols")
    assert hasattr(LanguagePlugin, "extract_calls")
    assert hasattr(LanguagePlugin, "extract_types")


def test_language_plugin_cannot_be_instantiated() -> None:
    """LanguagePlugin is abstract and must not be directly instantiable."""
    from llm_sca_tooling.graph.plugins.base import LanguagePlugin

    with pytest.raises(TypeError):
        LanguagePlugin()  # type: ignore[abstract]
