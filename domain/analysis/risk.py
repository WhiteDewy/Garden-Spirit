"""Risk —— 职业风险分析模块。

评估换工作/创业的风险：
- 凶星（土/火/天王/海王/冥）对事业行星（太阳/土星/十宫主）的紧张相位
- 十宫主失势/落陷 → 事业受阻
- 事业行星落 12 宫 → 隐性障碍
- 土星落 6 宫 → 工作负荷

产出：凶星相位事实 + 主题总结（career_risk）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import ASPECT_ZH
from shared.enums import DignityState, EvidencePolarity, FactCategory, Planet
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.knowledge import DignityEngine, load_knowledge

from domain.astrology.common import aspects_to, aspect_score, house_lord, theme_fact

logger = get_logger("analysis.risk")

# 凶星（土火为传统凶星，三王为世代压力）
_MALEFICS = {
    Planet.SATURN,
    Planet.MARS,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
}
# 事业关键目标
_RISK_TARGETS = {Planet.SUN, Planet.SATURN}


class Risk(AnalysisModule):
    name = "Risk"
    required_indicators = ["AspectQuality", "Lordship"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._dignity = DignityEngine(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        facts: list[Fact] = []
        score = 0.0
        mc_ruler = house_lord(chart, self._kb, 10)

        targets = _RISK_TARGETS | ({mc_ruler} if mc_ruler else set())

        # 1. 凶星对事业行星的紧张相位
        for target in targets:
            for aspect in aspects_to(chart, target, _MALEFICS):
                s = aspect_score(self._kb, aspect)
                if s >= 0:
                    continue  # 只记风险（负分）
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
                            "构成职业压力"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "body1": aspect.body1.value,
                            "body2": aspect.body2.value,
                            "aspect": aspect.aspect_type.value,
                            "orb": aspect.orb,
                            "applying": aspect.application.value,
                            "theme": "career_risk",
                            "module": self.name,
                        },
                    )
                )

        # 2. 十宫主尊贵异常（失势/落陷）
        if mc_ruler and mc_ruler in chart.planets:
            cp = chart.planets[mc_ruler]
            states, total = self._dignity.compute(
                mc_ruler, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
            )
            if any(s in (DignityState.DETRIMENT, DignityState.FALL) for s in states):
                score += -4
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.DIGNITY,
                        chart_id=chart.id,
                        description=(
                            f"十宫主{self._kb.planet(mc_ruler).name_zh}"
                            f"处于失势/落陷状态，事业根基承压"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "planet": mc_ruler.value,
                            "dignity": "detriment" if DignityState.DETRIMENT in states else "fall",
                            "score": -4,
                            "theme": "career_risk",
                            "module": self.name,
                        },
                    )
                )

        # 3. 事业行星落 12 宫 → 隐性障碍
        for planet in targets:
            if planet in chart.planets and chart.planets[planet].house.house == 12:
                score += 1.5
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.POSITION,
                        chart_id=chart.id,
                        description=(
                            f"{self._kb.planet(planet).name_zh}落在十二宫，"
                            "可能有未显化的隐性障碍"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={"planet": planet.value, "house": 12},
                    )
                )

        # 4. 土星落 6 宫 → 工作负荷风险
        if chart.planets.get(Planet.SATURN) and chart.planets[Planet.SATURN].house.house == 6:
            score += 1.0
            facts.append(
                Fact(
                    id=new_id("fact"),
                    category=FactCategory.POSITION,
                    chart_id=chart.id,
                    description="土星落在第六宫，日常工作负荷偏大",
                    extracted_at=datetime.now(timezone.utc),
                    payload={"planet": "saturn", "house": 6},
                )
            )

        # 5. 主题总结
        if facts:
            polarity = (
                EvidencePolarity.NEGATIVE if score > 1.0
                else EvidencePolarity.NEUTRAL
            )
            weight = min(4.0, max(0.5, abs(score)))
            facts.append(
                theme_fact(
                    chart, self.name, "career_risk",
                    polarity, weight, 0.65,
                    f"职业风险综合评分 {score:+.1f}（凶星相位与十宫压力）",
                    {"score": score},
                )
            )

        logger.info("Risk: 产出 %d 条事实, 风险分 %+.1f", len(facts), score)
        return facts
