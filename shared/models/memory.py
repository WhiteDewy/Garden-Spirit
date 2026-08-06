"""Memory：会话级对话记忆。"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import Role
from shared.types import EntityId


@dataclass(frozen=True)
class MemoryItem:
    """一条记忆：谁说了什么、何时。"""

    id: EntityId
    session_id: str
    role: Role
    content: str
    timestamp: datetime
    person_id: str = ""        # 跨会话查询需要；会话上下文记录时可留空
    metadata: dict[str, object] = field(default_factory=dict)
    # metadata 可含 {"intent_id": ..., "conclusion_id": ..., "tokens": 150}


@dataclass
class Memory:
    """会话级记忆。"""

    session_id: str
    person_id: str
    items: list[MemoryItem] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def add(self, item: MemoryItem) -> None:
        self.items.append(item)
        self.updated_at = datetime.now()

    def last_n(self, n: int) -> list[MemoryItem]:
        return self.items[-n:]

    def last_n_messages(self, n: int) -> list[MemoryItem]:
        """最近 n 条用户/助手消息（排除 system）。"""
        filtered = [m for m in self.items if m.role in (Role.USER, Role.ASSISTANT)]
        return filtered[-n:]

    def __len__(self) -> int:
        return len(self.items)
