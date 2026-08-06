"""花园日记（Journal）：用户的成长记录。

核心：每条日记可以关联一次咨询（related_intent/conclusion），
让"点击'离职' → 当时的咨询 → AI 建议 → 后来结果"的成长回看成为可能。

ai_summary 由写回管线生成（用户正文的浓缩成长记录），
用户可编辑；mood 是情绪标签（AI 识别或用户自选）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.types import EntityId


@dataclass
class JournalEntry:
    """一条花园日记。"""

    id: EntityId
    person_id: EntityId
    content: str                # 用户正文（可含 AI 生成草稿，用户编辑后覆盖）
    mood: str = ""              # 情绪标签，如 "迷茫" / "笃定" / "平静"
    ai_summary: str = ""        # AI 生成的成长记录（浓缩）
    related_intent_id: EntityId | None = None
    related_conclusion_id: EntityId | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = ["JournalEntry"]
