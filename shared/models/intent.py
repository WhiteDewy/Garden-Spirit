"""Intent 模型：领域验证后的用户意图。

**LLM 边界（原则三）**：LLM 从自然语言抽取原始 slots；
IntentRouter（Domain 规则）负责把 slots 校验、规范化并映射到 IntentDomain。
LLM 永不决定领域归属。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import IntentDomain
from shared.types import Confidence, EntityId


@dataclass
class IntentSlot:
    """一个从自然语言抽取的槽位。"""

    name: str                  # 槽名，如 "target_date" / "subject_planet"
    raw_value: str             # LLM 抽取的原始文本，如 "下个月"
    normalized_value: str      # Domain 规范化的值，如 "2026-09"
    confidence: Confidence = 1.0   # LLM 抽取置信度 0-1


@dataclass
class Intent:
    """领域验证后的意图。"""

    id: EntityId
    raw_query: str                      # 用户原始文本
    domain: IntentDomain                # Domain 判定，非 LLM 判定
    subdomain: str = ""                 # 如 "career_change" / "breakup_recovery"
    slots: dict[str, IntentSlot] = field(default_factory=dict)
    domain_confidence: float = 0.0      # Domain 规则匹配置信度
    parsed_at: datetime | None = None
    requires_clarification: bool = False   # Domain 无法高置信度映射时需要追问
    clarification_question: str = ""       # 追问问题

    # ---- 对话路由信号（Layer 1 富化产物；领域归属仍由 Domain 定） ----
    # intent_type: new_question | follow_up_deep_dive | clarification_response
    #              | topic_switch | confirmation | chat | meta
    intent_type: str = "new_question"
    focus_slice: str | None = None      # 用户点名的宫位切片（如"暗财/偏财/隐性收入"）
    deep_dive: bool = False             # 对上一轮某条切片的深挖追问
    confirmed: bool | None = None       # 仅 confirmation 意图：确认(True)/否认(False)

    # ---- 报告/观星台入口上下文（非占星结论；只用于路由、澄清、报告编译素材） ----
    entry_source: str | None = None
    entry_topic_key: str | None = None
    entry_primary_topic: str | None = None
    entry_secondary_topics: list[str] = field(default_factory=list)
    entry_intent_shape: str | None = None
    entry_report_type: str | None = None
    entry_user_focus_text: str | None = None

    def get_slot(self, name: str) -> IntentSlot | None:
        return self.slots.get(name)
