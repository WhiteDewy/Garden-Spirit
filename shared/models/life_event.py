"""LifeEvent：人生事件——成长时间轴的最小单元。

「成长页 = 人生时间轴」需要把三类东西统一进一条时间线：
- 用户人生事件（"真正辞职"）——用户手动记
- 咨询事件（"完成事业咨询"）——写回管线自动生成
- 日记（"写下一篇心情"）——写回管线自动生成

LifeEvent 是这条时间线的统一视图；JournalEntry 是日记的
可编辑内容本体（LifeEvent 通过 related_journal_id 引用它）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.types import EntityId


@dataclass
class LifeEvent:
    """一个时间轴事件。"""

    id: EntityId
    person_id: EntityId
    occurred_at: datetime       # 事件发生时间（排序键）
    label: str                  # 如 "真正辞职" / "完成事业咨询"
    kind: str = "life"          # "life"(用户事件) | "consult" | "journal" | "transit"
    detail: str = ""
    related_journal_id: EntityId | None = None
    related_intent_id: EntityId | None = None
    related_conclusion_id: EntityId | None = None
    # 咨询记录补意图/需求（喂记忆写回，Phase 1 剩余）：
    # domain = 八大领域（career/relationship/…），need = 诉求类型（heard/soothed/sorted/pushed）。
    domain: str = ""
    need: str = ""
    created_at: datetime | None = None


__all__ = ["LifeEvent"]
