"""Letter：星灵来信——信箱的最小单元。

每日一封（kind=daily）或咨询后一封（kind=consult_followup，V2）。
sender 表示来自哪位星灵/行星（如 "moon" / "sun" / "jupiter"）。
letter_date 是本地日期字符串（YYYY-MM-DD），作为每日幂等键。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.types import EntityId


@dataclass
class Letter:
    id: EntityId
    person_id: EntityId
    letter_date: str            # YYYY-MM-DD（本地日期，每日一封的幂等键）
    sender: str = "moon"        # 行星名："moon" / "sun" / "jupiter" ...
    title: str = ""
    body: str = ""
    kind: str = "daily"         # "daily" | "consult_followup"
    created_at: datetime | None = None
    read_at: datetime | None = None   # 用户打开信箱设已读（首页红点：今日来信未读）
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = ["Letter"]
