"""Long-horizon conversation memory (see §5.8 Additional gap)."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class ConversationTurn(StrictBaseModel):
    """A single turn in a conversation."""

    role: str  # "user" | "assistant"
    content: str
    turn_index: int
    created_ts: str


class ConversationMemory(StrictBaseModel):
    """SQLite-backed per-session conversation memory."""

    session_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    max_tokens: int = 8000
    compaction_threshold: float = 0.8
    created_ts: str
    updated_ts: str

    def add_turn(self, role: str, content: str) -> None:
        """Append a new turn and update *updated_ts*."""
        from llm_sca_tooling.storage.workspace import _now_ts

        turn = ConversationTurn(
            role=role,
            content=content,
            turn_index=len(self.turns),
            created_ts=_now_ts(),
        )
        self.turns.append(turn)
        self.updated_ts = _now_ts()

    def _estimate_tokens(self) -> int:
        return sum(len(t.content) // 4 for t in self.turns)

    def compact(self) -> None:
        """Sliding-window compaction: drop oldest turns when over threshold."""
        from llm_sca_tooling.storage.workspace import _now_ts

        while (
            self._estimate_tokens() > self.max_tokens * self.compaction_threshold
            and len(self.turns) > 2
        ):
            self.turns.pop(0)
            # Re-index remaining turns
            self.turns = [
                ConversationTurn(
                    role=t.role,
                    content=t.content,
                    turn_index=i,
                    created_ts=t.created_ts,
                )
                for i, t in enumerate(self.turns)
            ]
        self.updated_ts = _now_ts()

    def as_prompt_prefix(self, max_turns: int = 10) -> str:
        """Return bounded conversation history as a prompt prefix."""
        recent = self.turns[-max_turns:]
        lines = [f"{t.role.upper()}: {t.content}" for t in recent]
        return "\n".join(lines)
