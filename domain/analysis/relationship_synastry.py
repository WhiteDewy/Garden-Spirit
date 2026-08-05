"""RelationshipSynastry —— 双人合盘分析模块（基础版）。

对方行星 vs 我方行星的相位（复用 planet_pair 词库）+ 对方行星落我方宫位。
需要 partner_chart（params["partner_chart"]），无则返回空（Agent 应先追问）。

产出：
- synastry_chemistry     两星之间的连接（吸引/共鸣/滋养/张力）
- synastry_partner_role  对方如何牵动你的生活领域
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import ASPECT_ZH
from shared.enums import EvidencePolarity, FactCategory, Planet
from shared.models import Aspect, Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.calculation import SynastryCalculator
from domain.astrology.knowledge import load_knowledge

logger = get_logger("analysis.synastry")

_PAIR_POLARITY = {
    "HARMONIOUS": EvidencePolarity.POSITIVE,
    "DYNAMIC": EvidencePolarity.NEGATIVE,
    "NEUTRAL": EvidencePolarity.NEUTRAL,
}


class RelationshipSynastry(AnalysisModule):
    name = "RelationshipSynastry"
    required_indicators = ["AspectQuality"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._synastry = SynastryCalculator(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        partner_chart = params.get("partner_chart")
        if partner_chart is None:
            logger.warning("RelationshipSynastry 缺少 partner_chart，跳过")
            return []

        facts: list[Fact] = []

        # 1. 对方行星 vs 我方行星（优先级行星对）
        for pair in self._kb.synastry_priority_pairs:
            partner_p, my_p = Planet(pair[0]), Planet(pair[1])
            aspects = self._synastry.interchart_aspects(chart, partner_chart, [(partner_p, my_p)])
            for aspect in aspects:
                facts.append(self._aspect_fact(chart, partner_p, my_p, aspect))

        # 2. 对方行星落我方 5/7/8 等宫
        placements = self._synastry.partner_placements_in_my_houses(
            chart, partner_chart, self._kb.synastry_partner_houses
        )
        for placement in placements:
            facts.append(self._placement_fact(chart, placement))

        logger.info("RelationshipSynastry: 产出 %d 条事实", len(facts))
        return facts

    # ------------------------------------------------------------------

    def _aspect_fact(
        self, chart: Chart, partner_p: Planet, my_p: Planet, aspect: Aspect
    ) -> Fact:
        key = "_".join(sorted((partner_p.value, my_p.value)))
        entry = self._kb.planet_pairs.get(key, {})
        info = self._kb.aspects.get(aspect.aspect_type)
        nature = info.nature if info else "NEUTRAL"
        sentence = entry.get(
            "harmonious" if nature == "HARMONIOUS" else "dynamic" if nature == "DYNAMIC" else "base",
            entry.get("base", "彼此有天然的联结"),
        )
        polarity = _PAIR_POLARITY.get(nature, EvidencePolarity.NEUTRAL)
        weight = info.weight_multiplier if info else 0.8
        if aspect.application.value == "applying":
            weight *= 1.2
        elif aspect.application.value == "separating":
            weight *= 0.8
        confidence = max(0.5, min(0.9, 0.9 - aspect.orb * 0.05))

        desc = (
            f"对方的{self._kb.planet(partner_p).name_zh}对你的"
            f"{self._kb.planet(my_p).name_zh}形成"
            f"{ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)}——{sentence}"
        )
        return Fact(
            id=new_id("fact"),
            category=FactCategory.THEME,
            chart_id=chart.id,
            description=desc,
            extracted_at=datetime.now(timezone.utc),
            payload={
                "theme": "synastry_chemistry",
                "polarity": polarity.value,
                "weight": weight,
                "confidence": confidence,
                "module": self.name,
                "rule_id": f"synastry:{key}:{nature.lower()}",
            },
        )

    def _placement_fact(self, chart: Chart, placement) -> Fact:
        h_info = self._kb.house(placement.my_house)
        p_zh = self._kb.planet(placement.partner_planet).name_zh
        house_zh = h_info.name_zh
        kw = h_info.keywords_zh[0] if h_info.keywords_zh else "领域"
        desc = (
            f"对方的{p_zh}落在你的{house_zh}——TA会在你的{kw}领域里牵动你，"
            "这段关系与这一领域脱不开关系"
        )
        return Fact(
            id=new_id("fact"),
            category=FactCategory.THEME,
            chart_id=chart.id,
            description=desc,
            extracted_at=datetime.now(timezone.utc),
            payload={
                "theme": "synastry_partner_role",
                "polarity": EvidencePolarity.NEUTRAL.value,
                "weight": 1.0,
                "confidence": 0.75,
                "module": self.name,
                "rule_id": f"synastry:placement:{placement.partner_planet.value}:{placement.my_house}",
            },
        )
