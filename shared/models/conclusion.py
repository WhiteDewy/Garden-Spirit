"""Conclusion：Domain 生成的结论。完全无 LLM。

这是 Reasoner 的输出。由 EvidenceSet 完全确定性推导。
Conversation 层负责用人格 + LLM 把它包装成用户语言——
但绝不改变结论、极性或建议。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import ConclusionCategory, EvidencePolarity
from shared.types import Confidence, EntityId


@dataclass(frozen=True)
class Finding:
    """结论中的一条发现。引用证据。"""

    id: EntityId
    category: ConclusionCategory
    text: str                        # Domain 生成的陈述（无 LLM）
    polarity: EvidencePolarity
    confidence: Confidence
    supporting_evidence_ids: list[EntityId] = field(default_factory=list)
    weight: float = 0.0


@dataclass(frozen=True)
class TimePeriod:
    """一个突出的时间窗口（用于时机建议 / 人生 K 线）。"""

    label: str                       # 如 "2026年10月-12月"
    start: datetime
    end: datetime
    quality: EvidencePolarity        # 该窗口有利/不利
    key_events: list[str] = field(default_factory=list)  # 如 "木星过十宫"


@dataclass
class Conclusion:
    """领域生成的完整结论。"""

    id: EntityId
    intent_id: EntityId
    evidence_set_id: EntityId
    domain: str
    summary: str                     # 1-2 句领域生成摘要
    findings: list[Finding] = field(default_factory=list)
    overall_confidence: Confidence = 0.0
    overall_polarity: EvidencePolarity = EvidencePolarity.NEUTRAL
    time_periods: list[TimePeriod] = field(default_factory=list)  # 突出时间窗口
    recommendations: list[str] = field(default_factory=list)      # 结构化建议
    data_gaps: list[str] = field(default_factory=list)            # 缺失数据提示
    generated_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)
