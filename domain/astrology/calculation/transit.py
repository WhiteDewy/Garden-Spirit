"""行运计算器：行运行星 vs 本命行星的相位。

v1 方法论：本命 + 行运时间窗口（不做卜卦）。
Timing 分析模块通过本计算器扫描未来时间窗口内的行运相位。
"""

from __future__ import annotations

from datetime import datetime

from foundation.astronomy import ephemeris as swe_wrap
from foundation.logger import get_logger
from shared.constants import SE_PLANET_IDS
from shared.enums import AspectApplication, AspectType, Planet
from shared.models import Aspect, Chart

from domain.astrology.knowledge.loader import KnowledgeBase, load_knowledge

logger = get_logger("astrology.calculation")

# 行运参考行星（外行星 + 木星土星太阳——影响最持久）
_TRANSIT_SIGNIFICATORS = [
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
]


class TransitCalculator:
    """计算行运与本命之间的相位。"""

    def __init__(self, kb: KnowledgeBase | None = None):
        self._kb = kb or load_knowledge()

    def transit_aspects(
        self,
        natal: Chart,
        target: datetime,
        transit_bodies: list[Planet] | None = None,
    ) -> list[Aspect]:
        """某时刻行运行星对本命行星的相位。"""
        jd = swe_wrap.to_julian_day(target)
        bodies = transit_bodies or _TRANSIT_SIGNIFICATORS

        # 行运行星位置
        transit_positions = {}
        for p in bodies:
            if p in SE_PLANET_IDS:
                transit_positions[p] = swe_wrap.planet_full(jd, p)

        aspects: list[Aspect] = []
        natal_planets = natal.planets
        for t_body, t_data in transit_positions.items():
            t_lon = t_data["longitude"]
            t_speed = t_data["speed_deg_per_day"]
            for n_body, n_pos in natal_planets.items():
                n_lon = n_pos.ecliptic.longitude
                for aspect_type, info in self._kb.aspects.items():
                    orb = info.orb * 0.6  # 行运容许度收紧
                    sep = abs(((t_lon - n_lon + 540.0) % 360.0) - 180.0)
                    if abs(sep - info.angle) <= orb:
                        aspects.append(
                            Aspect(
                                body1=t_body,
                                body2=n_body,
                                aspect_type=aspect_type,
                                exact_angle=info.angle,
                                orb=abs(sep - info.angle),
                                application=self._application(
                                    t_lon, n_lon, t_speed, n_pos.speed_deg_per_day, info.angle
                                ),
                            )
                        )
        return aspects

    @staticmethod
    def _application(
        t_lon: float,
        n_lon: float,
        t_speed: float,
        n_speed: float,
        angle: float,
    ) -> AspectApplication:
        dt = 0.5
        sep0 = abs(((t_lon - n_lon + 540.0) % 360.0) - 180.0)
        sep1 = abs(
            (((t_lon + t_speed * dt) - (n_lon + n_speed * dt) + 540.0) % 360.0) - 180.0
        )
        orb0, orb1 = abs(sep0 - angle), abs(sep1 - angle)
        if orb1 < orb0 - 0.001:
            return AspectApplication.APPLYING
        if orb1 > orb0 + 0.001:
            return AspectApplication.SEPARATING
        return AspectApplication.EXACT
