"""Synastry 计算器 —— 双盘互照。

v1 范围（冻结决策）：基础合盘
- 对方行星 vs 我方行星的相位（interchart aspects）
- 对方行星落在我的宫位
不含 Composite/Davison。
"""

from __future__ import annotations

from dataclasses import dataclass

from foundation.logger import get_logger
from shared.enums import AspectApplication, Planet
from shared.models import Aspect, Chart

from domain.astrology.knowledge.loader import KnowledgeBase, load_knowledge

logger = get_logger("astrology.calculation")

# 合盘容许度收紧系数
_SYNASTRY_ORB_FACTOR = 0.6


@dataclass(frozen=True)
class PartnerHousePlacement:
    """对方某行星落在我的第几宫。"""

    partner_planet: Planet
    my_house: int


class SynastryCalculator:
    """基础合盘计算。"""

    def __init__(self, kb: KnowledgeBase | None = None):
        self._kb = kb or load_knowledge()

    def interchart_aspects(
        self,
        my_chart: Chart,
        partner_chart: Chart,
        pair_filter: list[tuple[Planet, Planet]] | None = None,
    ) -> list[Aspect]:
        """对方行星（body1）与我方行星（body2）的相位。

        Args:
            pair_filter: 只算这些行星对（对方, 我方）。None = 全部。
        """
        pairs = pair_filter or [
            (a, b)
            for a in partner_chart.planets
            for b in my_chart.planets
        ]
        aspects: list[Aspect] = []
        for partner_p, my_p in pairs:
            if partner_p not in partner_chart.planets or my_p not in my_chart.planets:
                continue
            p_lon = partner_chart.planets[partner_p].ecliptic.longitude
            m_lon = my_chart.planets[my_p].ecliptic.longitude
            p_speed = partner_chart.planets[partner_p].speed_deg_per_day
            m_speed = my_chart.planets[my_p].speed_deg_per_day

            for aspect_type, info in self._kb.aspects.items():
                orb = info.orb * _SYNASTRY_ORB_FACTOR
                if partner_p in (Planet.SUN, Planet.MOON) or my_p in (Planet.SUN, Planet.MOON):
                    orb += 1.5
                sep = abs(((p_lon - m_lon + 540.0) % 360.0) - 180.0)
                if abs(sep - info.angle) <= orb:
                    aspects.append(
                        Aspect(
                            body1=partner_p,
                            body2=my_p,
                            aspect_type=aspect_type,
                            exact_angle=info.angle,
                            orb=abs(sep - info.angle),
                            application=self._application(
                                p_lon, m_lon, p_speed, m_speed, info.angle
                            ),
                        )
                    )
        return aspects

    def partner_placements_in_my_houses(
        self, my_chart: Chart, partner_chart: Chart, focus_houses: list[int] | None = None
    ) -> list[PartnerHousePlacement]:
        """对方行星落在我的哪些宫位。"""
        placements: list[PartnerHousePlacement] = []
        for partner_p, cp in partner_chart.planets.items():
            my_house = self._assign_house(cp.ecliptic.longitude, my_chart.house_cusps)
            if focus_houses and my_house not in focus_houses:
                continue
            placements.append(PartnerHousePlacement(partner_planet=partner_p, my_house=my_house))
        return placements

    @staticmethod
    def _assign_house(longitude: float, cusps: dict[int, object]) -> int:
        """黄经 → 宫位（处理 0/360 回绕）。"""
        cs = [float(cusps[i].degree) for i in range(1, 13)]
        for i in range(12):
            a = cs[i]
            b = cs[(i + 1) % 12]
            if b < a:
                b += 360.0
            pos = longitude if longitude >= a else longitude + 360.0
            if a <= pos < b:
                return i + 1
        return 12

    @staticmethod
    def _application(
        p_lon: float, m_lon: float, p_speed: float, m_speed: float, angle: float
    ) -> AspectApplication:
        dt = 0.5
        sep0 = abs(((p_lon - m_lon + 540.0) % 360.0) - 180.0)
        sep1 = abs(
            (((p_lon + p_speed * dt) - (m_lon + m_speed * dt) + 540.0) % 360.0) - 180.0
        )
        orb0, orb1 = abs(sep0 - angle), abs(sep1 - angle)
        if orb1 < orb0 - 0.001:
            return AspectApplication.APPLYING
        if orb1 > orb0 + 0.001:
            return AspectApplication.SEPARATING
        return AspectApplication.EXACT
