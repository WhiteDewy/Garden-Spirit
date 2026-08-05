"""Finance —— 财务支撑分析模块（职业视角）。

评估换工作/创业的财务支撑：
- 2 宫主（正职收入）尊贵与落点
- 8 宫主（共同资源/他人资金，创业/跳槽涉及补偿、股权）
- 木星（扩张）与土星（积累）的财务意涵
- 2 宫主与吉/凶星的相位

产出：财务事实 + 主题总结（career_finance）。
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

logger = get_logger("analysis.finance")

_MALEFICS = {Planet.SATURN, Planet.MARS, Planet.PLUTO}
_BENEFICS = {Planet.JUPITER, Planet.VENUS}


class Finance(AnalysisModule):
    name = "Finance"
    required_indicators = ["Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._dignity = DignityEngine(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        facts: list[Fact] = []
        score = 0.0

        # 1. 2 宫主（正职收入）
        h2_lord = house_lord(chart, self._kb, 2)
        if h2_lord and h2_lord in chart.planets:
            cp = chart.planets[h2_lord]
            states, total = self._dignity.compute(
                h2_lord, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
            )
            score += total * 0.8
            if total != 0:
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.DIGNITY,
                        chart_id=chart.id,
                        description=(
                            f"二宫主{self._kb.planet(h2_lord).name_zh}"
                            f"落在{self._kb.sign(cp.sign.sign).name_zh}，"
                            f"财务尊贵分{total:+d}"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "planet": h2_lord.value,
                            "sign": cp.sign.sign.value,
                            "dignity": self._top_dignity(states).value,
                            "score": total,
                            "theme": "career_finance",
                            "module": self.name,
                        },
                    )
                )
            # 2 宫主落角宫（1/4/7/10）→ 收入显化
            if cp.house.house in (1, 4, 7, 10):
                score += 1.5
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.POSITION,
                        chart_id=chart.id,
                        description=(
                            f"二宫主{self._kb.planet(h2_lord).name_zh}"
                            f"落在{cp.house.house}宫，收入显化度较高"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={"planet": h2_lord.value, "house": cp.house.house},
                    )
                )

        # 2. 8 宫主（共同资源/他人资金）
        h8_lord = house_lord(chart, self._kb, 8)
        if h8_lord and h8_lord in chart.planets:
            total = self._dignity_total(h8_lord, chart)
            score += total * 0.5
            if abs(total) >= 2:
                facts.append(
                    Fact(
                        id=new_id("fact"),
                        category=FactCategory.LORDSHIP,
                        chart_id=chart.id,
                        description=(
                            f"八宫主{self._kb.planet(h8_lord).name_zh}"
                            f"尊贵分{total:+d}，共同资源/他方资金支持"
                            + ("良好" if total > 0 else "受限")
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={"ruler": h8_lord.value, "score": total},
                    )
                )

        # 3. 木星（扩张）与土星（积累）的财务相位
        for target in (Planet.JUPITER, Planet.SATURN):
            if target not in chart.planets:
                continue
            for aspect in aspects_to(chart, target, _BENEFICS | _MALEFICS):
                s = aspect_score(self._kb, aspect)
                if abs(s) < 0.3:
                    continue
                score += s * 0.6
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
                            "影响财务"
                        ),
                        extracted_at=datetime.now(timezone.utc),
                        payload={
                            "body1": aspect.body1.value,
                            "body2": aspect.body2.value,
                            "aspect": aspect.aspect_type.value,
                            "orb": aspect.orb,
                            "applying": aspect.application.value,
                            "theme": "career_finance",
                            "module": self.name,
                        },
                    )
                )

        # 4. 主题总结
        if facts:
            polarity = (
                EvidencePolarity.POSITIVE if score > 1.0
                else EvidencePolarity.NEGATIVE if score < -1.0
                else EvidencePolarity.NEUTRAL
            )
            weight = min(4.0, max(0.5, abs(score)))
            facts.append(
                theme_fact(
                    chart, self.name, "career_finance",
                    polarity, weight, 0.6,
                    f"财务支撑评分 {score:+.1f}（二宫收入与资源位势）",
                    {"score": score},
                )
            )

        logger.info("Finance: 产出 %d 条事实, 财务分 %+.1f", len(facts), score)
        return facts

    # ------------------------------------------------------------------

    def _dignity_total(self, planet: Planet, chart: Chart) -> int:
        if planet not in chart.planets:
            return 0
        cp = chart.planets[planet]
        _states, total = self._dignity.compute(
            planet, cp.sign.sign, cp.sign.degree_in_sign, chart.sect
        )
        return total

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
