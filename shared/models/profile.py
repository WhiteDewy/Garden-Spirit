"""ChartProfile：盘主长期画像（第四层记忆的核心）。

跨会话累积的对"这个用户"的占星理解——不是数据 dump，而是可被
LLM 转述、被前端"我的宇宙"页消费的浓缩画像。

与 Memory（会话级逐条记忆）的关系：
- Memory: 时间线（谁在何时说了什么）——已有。
- ChartProfile: 沉淀（长期理解的结论）——本文件。

画像由"咨询后写回"管线更新（application/memory 层），
Domain 不直接写画像（原则：Application 负责编排跨会话状态）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.types import Confidence, EntityId


@dataclass
class DomainSummary:
    """一个意图领域的长期理解。对应前端"我的宇宙"的单个领域卡片。"""

    domain: str                 # 如 "career" / "relationship" / "wealth" / "emotion"
    summary: str                # 累积理解（人话）："最近三个月你越来越相信自己的判断"
    confidence: Confidence = 0.0
    #: 支撑这条理解的要点（证据/星象依据的人话版本）
    evidence_notes: list[str] = field(default_factory=list)
    updated_at: datetime | None = None


@dataclass
class VerifiedFinding:
    """一条已沉淀的占星判断（本命结构层面，非临时结论）。

    v1 由写回管线从结论自动生成；验前事系统（B1）用人生事件/用户反馈
    确认或反驳它，校准 confidence 并记录验证痕迹。
    """

    id: EntityId
    statement: str              # 如 "土星落九宫：深造/远行是你职业跃迁的必经之路"
    confidence: Confidence = 0.0
    source_intent_id: EntityId | None = None
    confirmed_at: datetime | None = None
    user_feedback: str = ""     # "" 未反馈 | "confirmed" | "refuted"
    #: 验前事痕迹：如 "2026-08-06 事件「辞职」验证通过（土星主运）"
    verification_notes: list[str] = field(default_factory=list)
    #: 所属意图领域（写回时从 intent.domain 填入；旧数据可能为空 = 未分类）
    domain: str = ""


@dataclass
class KeyDate:
    """画像里记住的重要日期（用于"上次我们聊到…"和成长时间轴）。"""

    id: EntityId
    date: datetime
    label: str                  # 如 "考虑离职" / "完成事业咨询"
    kind: str = "event"         # "event"(人生事件) | "consult"(咨询) | "transit"(行运)
    related_intent_id: EntityId | None = None


@dataclass
class ChartProfile:
    """盘主画像。每个 Person 一条。"""

    person_id: EntityId
    #: 行星/宫位层面的累积观察。key 用 snake_case，如 "moon_in_7"、"saturn_house_lord_9"
    lord_states: dict[str, object] = field(default_factory=dict)
    verified_findings: list[VerifiedFinding] = field(default_factory=list)
    key_dates: list[KeyDate] = field(default_factory=list)
    #: 领域摘要。key = IntentDomain.value
    domain_summaries: dict[str, DomainSummary] = field(default_factory=dict)
    #: 关系层（A2）：信任分与驱动信号计数。等级由 RelationshipService 从分数推导，
    #: 不落库（单一事实源）。信号 key：deep_consult/quick_consult/casual_chat/journal/finding_confirmed/finding_refuted
    trust_score: float = 0.0
    trust_signals: dict[str, int] = field(default_factory=dict)
    #: 用户偏好（B2 行动层）：push_frequency / sensitive_topics / preferred_persona。
    #: 灵活 dict，校验在 API 边界，避免模型层与产品字段耦合。
    preferences: dict[str, object] = field(default_factory=dict)
    #: 34 子类点亮（随聊记录层，self_map_design §2）。key = 子类 id（如 "moon_tide"），
    #: value = 深度分（提及+1/倾诉+3/咨询反向+10）。只记录话题，不声称用户属性（硬线）。
    fragments: dict[str, int] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = ["ChartProfile", "DomainSummary", "VerifiedFinding", "KeyDate"]
