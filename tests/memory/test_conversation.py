"""Tests for ConversationMemory long-horizon session memory."""

from __future__ import annotations


def test_conversation_memory_add_turn() -> None:
    """add_turn appends turns with correct role ordering."""
    from llm_sca_tooling.memory.conversation import ConversationMemory

    mem = ConversationMemory(
        session_id="s1",
        created_ts="2026-01-01T00:00:00Z",
        updated_ts="2026-01-01T00:00:00Z",
    )
    mem.add_turn("user", "hello")
    mem.add_turn("assistant", "hi")
    assert len(mem.turns) == 2
    assert mem.turns[0].role == "user"


def test_conversation_memory_compact() -> None:
    """compact() should reduce turn count when over threshold."""
    from llm_sca_tooling.memory.conversation import ConversationMemory

    mem = ConversationMemory(
        session_id="s1",
        created_ts="2026-01-01T00:00:00Z",
        updated_ts="2026-01-01T00:00:00Z",
        max_tokens=10,
    )
    for i in range(20):
        mem.add_turn("user", f"{'x' * 100} {i}")
    mem.compact()
    assert len(mem.turns) < 20


def test_conversation_memory_prompt_prefix() -> None:
    """as_prompt_prefix returns correctly formatted conversation lines."""
    from llm_sca_tooling.memory.conversation import ConversationMemory

    mem = ConversationMemory(
        session_id="s1",
        created_ts="2026-01-01T00:00:00Z",
        updated_ts="2026-01-01T00:00:00Z",
    )
    mem.add_turn("user", "what is X?")
    mem.add_turn("assistant", "X is Y")
    prefix = mem.as_prompt_prefix()
    assert "USER: what is X?" in prefix
    assert "ASSISTANT: X is Y" in prefix
