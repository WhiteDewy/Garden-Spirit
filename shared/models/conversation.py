"""Conversation：完整对话会话。"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import PersonaType
from shared.types import EntityId


@dataclass(frozen=True)
class DialogueTurn:
    """一轮完整交流：用户消息 + 助手回复。"""

    id: EntityId
    user_message: str
    assistant_response: str
    intent_id: EntityId | None = None
    conclusion_id: EntityId | None = None
    persona_used: PersonaType | None = None
    timestamp: datetime | None = None
    latency_ms: int = 0
    tokens_used: int = 0


@dataclass
class Conversation:
    """一个完整对话会话。"""

    id: EntityId
    person_id: EntityId
    persona: PersonaType
    turns: list[DialogueTurn] = field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    is_active: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

    def add_turn(self, turn: DialogueTurn) -> None:
        self.turns.append(turn)

    def last_conclusion_id(self) -> EntityId | None:
        """最近一轮有 conclusion 的 id。"""
        for turn in reversed(self.turns):
            if turn.conclusion_id:
                return turn.conclusion_id
        return None
