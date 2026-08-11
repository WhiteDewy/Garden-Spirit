"""shared/models/fragment_light —— 34 子类点亮账本条目（成长复利层的地基）。

self_map_design §4/§2.5：累计深度仍以 ChartProfile.fragments 为单一事实源
（零迁移、向后兼容）；本账本是"追加式事件日志"，每次点亮记一条，
供今日灵魂碎片 / 成长报告 / 格子反转 / 行运微亮按时间聚合。

跨层契约：Application 层产出（FragmentService.light 的 ledger 累加器），
Foundation 层持久化（GardenStore.append_fragment_lights）——故放 shared/models。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FragmentLight:
    """一次点亮事件：哪个子类、加了多少深度、什么方式、来源摘录、何时。

    - kind：点亮方式（FragmentLightKind 值），mention/outpouring/consult/seen/action。
    - source：来源摘录（用户消息片段等，含 PII，落库时加密，纯非敏感字段明文）。
    - session_id：所属会话（conversation.id）。落库时由 append_fragment_lights 统一盖章
      （本轮所有点亮都属于当前会话），供"上一段会话点亮的子类"精确回溯（§4.2 触发行动）。
    """

    subtype_id: str
    delta: int
    kind: str = "mention"
    source: str = ""
    lit_at: datetime | None = None
    session_id: str = ""


__all__ = ["FragmentLight"]
