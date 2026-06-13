"""Completion-callable factory (provider wiring)."""

from __future__ import annotations

import pytest

from llm_sca_tooling.llm import (
    CompletionUnavailable,
    completion_available,
    get_completion_callable,
)
from llm_sca_tooling.llm.completion import DEFAULT_MODEL_ID, resolve_model_id


class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self, blocks: list[_Block], stop_reason: str = "end_turn") -> None:
        self.content = blocks
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def create(self, **kwargs) -> _Response:
        self.calls.append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response: _Response) -> None:
        self.messages = _Messages(response)


def test_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert completion_available() is False
    with pytest.raises(CompletionUnavailable):
        get_completion_callable()


def test_model_resolution(monkeypatch) -> None:
    monkeypatch.delenv("LLM_SCA_MODEL", raising=False)
    assert resolve_model_id() == DEFAULT_MODEL_ID
    monkeypatch.setenv("LLM_SCA_MODEL", "claude-haiku-4-5")
    assert resolve_model_id() == "claude-haiku-4-5"
    assert resolve_model_id("explicit-model") == "explicit-model"


def test_injected_client_completes() -> None:
    client = _FakeClient(_Response([_Block("hello "), _Block("world")]))
    complete = get_completion_callable("test-model", client=client)
    assert complete("prompt text") == "hello world"
    call = client.messages.calls[0]
    assert call["model"] == "test-model"
    assert call["messages"] == [{"role": "user", "content": "prompt text"}]


def test_refusal_returns_empty_string() -> None:
    client = _FakeClient(_Response([], stop_reason="refusal"))
    complete = get_completion_callable("test-model", client=client)
    # Fail-closed: boundaries parse "" as no evidence and fall back to null.
    assert complete("prompt") == ""


class _RaisingMessages:
    def create(self, **kwargs):
        raise RuntimeError("simulated provider outage")


class _RaisingClient:
    messages = _RaisingMessages()


def test_provider_exception_fails_closed_to_empty() -> None:
    complete = get_completion_callable("test-model", client=_RaisingClient())
    # One provider/network failure must not abort a multi-clause run;
    # boundaries parse "" as "no evidence" and fall back to null adapters.
    assert complete("prompt") == ""
