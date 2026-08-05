"""Daily —— 每日运势分析模块。

基于今日行运（月亮/太阳/水星/金星/火星）对本命行星的相位，
按本命行星落宫映射到生活领域。快速行星给出"今天"的能量天气。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import ASPECT_ZH
from shared.enums import EvidencePolarity, FactCategory, Planet
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.calculation import TransitCalculator
from domain.astrology.knowledge import load_knowledge

logger = get_logger("analysis.daily")

# 每日主看快速行星（月亮=情绪天气，太阳=活力，水/金/火=沟通/爱/行动）
_DAILY_SIGNIFICATORS = [
    Planet.MOON,
    Planet.SUN,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
]

# 每日解读的目标本命行星（排除交点/莉莉丝等特殊点，避免噪音）
_DAILY_TARGETS = {
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
}

_POLARITY = {
    "HARMONIOUS": EvidencePolarity.POSITIVE,
    "DYNAMIC": EvidencePolarity.NEGATIVE,
    "NEUTRAL": EvidencePolarity.NEUTRAL,
}

_MAX_FACTS = 6


class Daily(AnalysisModule):
    name = "Daily"
    required_indicators = ["AspectQuality", "Timing"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._transit = TransitCalculator(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        today = datetime.now(timezone.utc)
        aspects = self._transit.transit_aspects(chart, today, _DAILY_SIGNIFICATORS)

        facts: list[Fact] = []
        for aspect in aspects:
            natal_p = aspect.body2
            if natal_p not in _DAILY_TARGETS or natal_p not in chart.planets:
                continue
            house = chart.planets[natal_p].house.house
            area = self._area_label(house)
            info = self._kb.aspects.get(aspect.aspect_type)
            if info is None:
                continue
            polarity = _POLARITY.get(info.nature, EvidencePolarity.NEUTRAL)
            weight = info.weight_multiplier
            if aspect.application.value == "applying":
                weight *= 1.2
            confidence = max(0.5, min(0.9, 0.9 - aspect.orb * 0.05))

            t_zh = self._kb.planet(aspect.body1).name_zh
            p_zh = self._kb.planet(natal_p).name_zh
            a_zh = ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)
            facts.append(
                Fact(
                    id=new_id("fact"),
                    category=FactCategory.THEME,
                    chart_id=chart.id,
                    description=(
                        f"今日{t_zh}对你本命的{p_zh}形成{a_zh}"
                        f"——影响你的{area}领域"
                    ),
                    extracted_at=datetime.now(timezone.utc),
                    payload={
                        "theme": f"daily_{house}",
                        "polarity": polarity.value,
                        "weight": weight,
                        "confidence": confidence,
                        "module": self.name,
                        "rule_id": f"daily:{aspect.body1.value}:{aspect.body2.value}:{aspect.aspect_type.value}",
                    },
                )
            )

        # 只保留最显著的前几条
        facts.sort(key=lambda f: abs(f.payload["weight"]) * f.payload["confidence"], reverse=True)
        logger.info("Daily: 今日 %d 条显著行运", len(facts))
        return facts[:_MAX_FACTS]

    def _area_label(self, house: int) -> str:
        h_info = self._kb.house(house)
        return h_info.keywords_zh[0] if h_info.keywords_zh else "生活"
