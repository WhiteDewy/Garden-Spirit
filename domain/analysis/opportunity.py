"""Opportunity —— 职业机会分析模块。

评估机会与贵人支持：
- 吉星（木/金/日）对事业行星（太阳/土星/十宫主）的助力相位
- 木星尊贵 → 扩张与好运
- 11 宫（人脉/贵人）主星状态
- 2 宫（收入机会）主星状态

产出：助力相位事实 + 主题总结（career_opportunity）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import ASPECT_ZH, DIGNITY_STATE_ZH
from shared.enums import DignityState, EvidencePolarity, FactCategory, Planet
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule, focus_planets_from_enrichment
from domain.astrology.knowledge import DignityEngine, load_knowledge

from domain.astrology.common import aspects_to, aspect_score, assess_planet, house_lord, theme_fact

logger = get_logger("analysis.opportunity")

# 吉星
_BENEFICS = {Planet.JUPITER, Planet.VENUS, Planet.SUN}
_OPPORTUNITY_TARGETS = {Planet.SUN, Planet.SATURN, Planet.JUPITER}


class Opportunity(AnalysisModule):
    name = "Opportunity"
    required_indicators = ["AspectQuality", "Lordship", "SupportResources"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._dignity = DignityEngine(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        facts: list[Fact] = []
        score = 0.0
        mc_ruler = house_lord(chart, self._kb, 10)

        targets = _OPPORTUNITY_TARGETS | ({mc_ruler} if mc_ruler else set())
        targets.update(
            focus_planets_from_enrichment(
                chart,
                self._kb,
                params.get("_enrichment"),
                include_house_lords=True,
                include_focus_houses=True,
            )
        )

        # 1. 吉星对事业行星的助力相位
        for target in targets:
            for aspect in aspects_to(chart, target, _BENEFICS):
                s = aspect_score(self._kb, aspect)
                if s <= 0:
                    continue
                score += s
                other = aspect.body2 if aspect.body1 == target else aspect.body1
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.ASPECT,
                        chart_id=chart.id,
                        description=(
                            f"{self._kb.planet(other).name_zh}对你的"
                            f"{self._kb.planet(target).name_zh}形成"
                            f"{ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)}，"
                            "带来助力"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "body1": aspect.body1.value,
                            "body2": aspect.body2.value,
                            "aspect": aspect.aspect_type.value,
                            "orb": aspect.orb,
                            "applying": aspect.application.value,
                            "theme": "career_opportunity",
                            "module": self.name,
                        },
                    )
                )

        # 2. 木星尊贵（扩张/好运）
        jup = chart.planets.get(Planet.JUPITER)
        if jup:
            states, _ = self._dignity.compute(
                Planet.JUPITER, jup.sign.sign, jup.sign.degree_in_sign, chart.sect
            )
            jup_assessment = assess_planet(chart, self._kb, Planet.JUPITER)
            total = self._raw_essential_score(jup_assessment)
            if total >= 3 and jup_assessment.essential_neg == 0:
                top_dignity = self._top_dignity(states)
                dignity_label = DIGNITY_STATE_ZH.get(top_dignity.value, top_dignity.value)
                score += total
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.DIGNITY,
                        chart_id=chart.id,
                        description=(
                            f"木星落在{jup.sign.sign.value}，{dignity_label}，"
                            "扩张与机遇气场强"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "planet": "jupiter",
                            "sign": jup.sign.sign.value,
                            "dignity": top_dignity.value,
                            "score": total,
                            "raw_score": total,
                            "essential_pos": jup_assessment.essential_pos,
                            "essential_neg": jup_assessment.essential_neg,
                            "theme": "career_opportunity",
                            "module": self.name,
                        },
                    )
                )

        # 3. 11 宫主（人脉/贵人）
        h11_lord = house_lord(chart, self._kb, 11)
        if h11_lord and h11_lord in chart.planets:
            h11_assessment = assess_planet(chart, self._kb, h11_lord)
            total = self._raw_essential_score(h11_assessment)
            h11_strong = h11_assessment.essential_pos > 0 and h11_assessment.essential_neg == 0
            h11 = chart.planets[h11_lord].house.house
            if (total >= 2 and h11_strong) or h11 == 11 or h11 == 1:
                score += 2.0
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.LORDSHIP,
                        chart_id=chart.id,
                        description=(
                            f"十一宫主{self._kb.planet(h11_lord).name_zh}"
                            f"落在{h11}宫，人脉贵人位势良好"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={"ruler": h11_lord.value, "ruler_house": h11},
                    )
                )

        # 4. 2 宫主（收入机会）
        h2_lord = house_lord(chart, self._kb, 2)
        if h2_lord and h2_lord in chart.planets:
            cp = chart.planets[h2_lord]
            states, _ = self._dignity.compute(
                h2_lord, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
            )
            h2_assessment = assess_planet(chart, self._kb, h2_lord)
            total = self._raw_essential_score(h2_assessment)
            if total >= 2 and h2_assessment.essential_pos > 0 and h2_assessment.essential_neg == 0:
                top_dignity = self._top_dignity(states)
                dignity_label = DIGNITY_STATE_ZH.get(top_dignity.value, top_dignity.value)
                score += 1.5
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.LORDSHIP,
                        chart_id=chart.id,
                        description=(
                            f"二宫主{self._kb.planet(h2_lord).name_zh}{dignity_label}，"
                            "收入机会有支撑"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "ruler": h2_lord.value,
                            "score": total,
                            "raw_score": total,
                            "essential_pos": h2_assessment.essential_pos,
                            "essential_neg": h2_assessment.essential_neg,
                            "theme": "career_opportunity",
                            "module": self.name,
                        },
                    )
                )

        # 5. 主题总结
        if facts:
            polarity = (
                EvidencePolarity.POSITIVE if score > 1.0
                else EvidencePolarity.NEUTRAL
            )
            weight = min(4.0, max(0.5, abs(score)))
            facts.append(
                theme_fact(
                    chart, self.name, "career_opportunity",
                    polarity, weight, 0.65,
                    (
                        "职业机会侧有外部助力可以借用"
                        if score > 1.0
                        else "职业机会侧暂时以观察和铺垫为主"
                    ) + "（吉星助力与人脉位势）",
                    {"score": score},
                )
            )

        logger.info("Opportunity: 产出 %d 条事实, 机会分 %+.1f", len(facts), score)
        return facts

    # ------------------------------------------------------------------

    @staticmethod
    def _raw_essential_score(assessment) -> int:
        """展示/审计用原始本质分：由公共 assess_planet 本质轴反推，避免第二套评分。"""
        return round((assessment.essential_pos - assessment.essential_neg) / 0.35)

    @staticmethod
    def _top_dignity(states: list[DignityState]) -> DignityState:
        order = [
            DignityState.DOMICILE,
            DignityState.EXALTATION,
            DignityState.TRIPLICITY,
            DignityState.TERM,
            DignityState.FACE,
        ]
        for state in order:
            if state in states:
                return state
        return states[0] if states else DignityState.PEREGRINE
