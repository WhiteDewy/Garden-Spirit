"""Timeline —— 人生 K 线模型。

窗口扫描的产出：未来一段时间内，机会分与压力分随时间的曲线。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import EvidencePolarity
from shared.types import EntityId


@dataclass
class TimelineWindow:
    """一个时间窗口的机会/压力快照。"""

    start: datetime
    end: datetime
    opportunity_score: float      # 吉星助力分（正）
    pressure_score: float         # 凶星压力分（正，绝对值）
    quality: EvidencePolarity     # 窗口总体倾向
    key_transits: list[str] = field(default_factory=list)  # 主要行运描述

    @property
    def net_score(self) -> float:
        return self.opportunity_score - self.pressure_score


@dataclass
class Timeline:
    """未来时间窗的人生 K 线。"""

    person_id: EntityId
    chart_id: EntityId
    label: str                    # 如 "职业 K 线 · 未来 12 个月"
    windows: list[TimelineWindow] = field(default_factory=list)
    generated_at: datetime | None = None

    @property
    def best_window(self) -> TimelineWindow | None:
        if not self.windows:
            return None
        return max(self.windows, key=lambda w: w.net_score)

    @property
    def worst_window(self) -> TimelineWindow | None:
        if not self.windows:
            return None
        return min(self.windows, key=lambda w: w.net_score)

    @property
    def overall_quality(self) -> EvidencePolarity:
        if not self.windows:
            return EvidencePolarity.NEUTRAL
        total = sum(w.net_score for w in self.windows)
        if total > 1.0:
            return EvidencePolarity.POSITIVE
        if total < -1.0:
            return EvidencePolarity.NEGATIVE
        return EvidencePolarity.NEUTRAL
