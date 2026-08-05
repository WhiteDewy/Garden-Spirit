"""CareerStrength —— 职业强度分析模块。

聚焦：10 宫（事业）、6 宫（日常工作）、土星（成就）、太阳（野心）、
MC 守护星。产出机械事实（DIGNITY/ASPECT）+ 主题总结（THEME）。

加权与极性交给 Evidence 层（原则三），本模块只产出事实。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import DIGNITY_STATE_ZH
from shared.enums import DignityState, EvidencePolarity, FactCategory, Planet, Sign
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.knowledge import DignityEngine, load_knowledge

logger = get_logger("analysis.career_strength")

# 事业关键行星
_CAREER_PLANETS = [Planet.SATURN, Planet.SUN, Planet.JUPITER, Planet.MERCURY]


class CareerStrength(AnalysisModule):
    name = "CareerStrength"
    required_indicators = ["PlanetStrength", "Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._dignity = DignityEngine(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        facts: list[Fact] = []

        # 1. MC 守护星
        mc_ruler = self._mc_ruler(chart)
        if mc_ruler:
            facts.append(
                Fact(
                    id=new_id("fact"),
                    category=FactCategory.LORDSHIP,
                    chart_id=chart.id,
                    description=f"第十宫守护星是{self._kb.planet(mc_ruler).name_zh}",
                    extracted_at=datetime.now(timezone.utc),
                    payload={"type": "mc_ruler", "ruler": mc_ruler.value, "house": 10},
                )
            )

        # 2. 事业行星的先天尊贵
        for planet in _CAREER_PLANETS:
            if planet not in chart.planets:
                continue
            cp = chart.planets[planet]
            states, total = self._dignity.compute(
                planet, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
            )
            # 只输出显著的尊贵状态
            significant = [s for s in states if self._dignity.score(s) != 0]
            if significant:
                # 取最显著一档（按 |score|）
                top = max(significant, key=lambda s: abs(self._dignity.score(s)))
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.DIGNITY,
                        chart_id=chart.id,
                        description=(
                            f"{self._kb.planet(planet).name_zh}落在"
                            f"{self._kb.sign(cp.sign.sign).name_zh}"
                            f"{cp.sign.degree_in_sign:.1f}°，"
                            f"{DIGNITY_STATE_ZH.get(top.value, top.value)}"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "planet": planet.value,
                            "sign": cp.sign.sign.value,
                            "dignity": top.value,
                            "score": self._dignity.score(top),
                            "theme": "career_strength",
                        },
                    )
                )

        # 3. 事业行星落 10 宫（角宫强化）
        for planet in _CAREER_PLANETS:
            if planet in chart.planets and chart.planets[planet].house.house == 10:
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.POSITION,
                        chart_id=chart.id,
                        description=(
                            f"{self._kb.planet(planet).name_zh}落在第十宫，"
                            "强化事业主题"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={"planet": planet.value, "house": 10},
                    )
                )

        # 4. 主题总结（聚合职业强度）
        theme_fact = self._theme_summary(chart, mc_ruler)
        if theme_fact:
            facts.append(theme_fact)

        logger.info("CareerStrength: 产出 %d 条事实", len(facts))
        return facts

    # ------------------------------------------------------------------

    def _mc_ruler(self, chart: Chart) -> Planet | None:
        """第十宫守护星 = MC 星座的守护行星。"""
        if chart.midheaven is None:
            return None
        mc_sign: Sign = chart.midheaven.sign
        return self._kb.sign(mc_sign).traditional_ruler

    def _theme_summary(self, chart: Chart, mc_ruler: Planet | None) -> Fact | None:
        """聚合职业强度：分数 = Σ(事业行星尊贵分) + 落十宫加成。"""
        score = 0.0
        details: list[str] = []

        for planet in _CAREER_PLANETS:
            if planet not in chart.planets:
                continue
            cp = chart.planets[planet]
            states, total = self._dignity.compute(
                planet, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
            )
            score += total
            if cp.house.house == 10:
                score += 2
                details.append(f"{self._kb.planet(planet).name_zh}落十宫")

        if mc_ruler and mc_ruler in chart.planets:
            mcr = chart.planets[mc_ruler]
            states, total = self._dignity.compute(
                mc_ruler, mcr.sign.sign, mcr.sign.degree_in_sign, chart.sect
            )
            score += total
            details.append(f"十宫主{self._kb.planet(mc_ruler).name_zh}尊贵分{total}")

        if not details:
            return None

        # 分数 → 极性（分数由尊贵权值决定，全部来自 Domain）
        if score >= 3:
            polarity = EvidencePolarity.POSITIVE
            weight = min(5.0, abs(score))
        elif score <= -3:
            polarity = EvidencePolarity.NEGATIVE
            weight = min(5.0, abs(score))
        else:
            polarity = EvidencePolarity.NEUTRAL
            weight = 0.5

        confidence = 0.7
        return Fact(
            id=new_id("fact"),
            category=FactCategory.THEME,
            chart_id=chart.id,
            description=f"职业强度综合评分 {score:.0f}（{'；'.join(details)}）",
            extracted_at=datetime.now(timezone.utc),
            payload={
                "theme": "career_strength",
                "polarity": polarity.value,
                "weight": weight,
                "confidence": confidence,
                "score": score,
                "module": self.name,
            },
        )
