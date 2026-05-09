from __future__ import annotations

from llm_sca_tooling.errors import ConfigError, LLMSCAError, NotImplementedFeatureError


def test_errors_share_base_type() -> None:
    assert issubclass(ConfigError, LLMSCAError)
    assert issubclass(NotImplementedFeatureError, LLMSCAError)
