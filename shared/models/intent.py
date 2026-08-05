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

    def get_slot(self, name: str) -> IntentSlot | None:
        return self.slots.get(name)
