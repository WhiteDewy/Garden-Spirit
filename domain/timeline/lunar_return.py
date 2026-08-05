"""月返（Lunar Return）计算器。

月返 = 月亮回到本命月亮黄经的时刻起的盘，代表"接下来一个月"的主基调。
排盘逻辑（docs/astrology_lunar_return.md）：
① 本命月亮黄经 → ② 正向求最近一次月返时刻（参考时刻之前）
③ 以【当前所在地】排返回盘 → ④ 判读（月亮落宫/上升/角宫群星）
确定性、无 LLM；结果可 to_dict() 序列化（出口，供 app 消费）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from foundation.astronomy.ephemeris import planet_longitude, to_julian_day
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, Chart, GeoLocation, Person

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline.returns import classify_return_location, find_return_after, find_return_before

# 月亮运行 ~13°/天
_MOON_SCAN_DAYS = 40          # 往回扫 40 天（覆盖 >1 个完整月返周期）


def _moon_lon(dt: datetime) -> float:
    return planet_longitude(to_julian_day(dt), Planet.MOON)


@dataclass
class LunarReturn:
    """一次月返。"""

    moment: datetime             # 月返时刻（UTC）
    effective_until: datetime    # 下次月返（生效截止）
    chart: Chart                 # 返回盘
    location_zh: str = ""
    location_type: str = "current_place"   # birth_place / current_place

    def to_dict(self) -> dict:
        """出口：JSON 友好的关键点（供星灵 app 消费）。"""
        planets = self.chart.planets
        moon = planets[Planet.MOON]
        houses: dict[int, list[str]] = {h: [] for h in range(1, 13)}
        for pl, cp in planets.items():
            if pl == Planet.SOUTH_NODE:
                continue
            houses.setdefault(cp.house.house, []).append(pl.value)
        return {
            "type": "lunar_return",
            "moment": self.moment.isoformat(),
            "effective_until": self.effective_until.isoformat(),
            "location": self.location_zh,
            "location_type": self.location_type,
            "ascendant": f"{self.chart.ascendant.sign.value} {self.chart.ascendant.degree_in_sign:.1f}",
            "ascendant_sign": self.chart.ascendant.sign.value,
            "midheaven_sign": self.chart.midheaven.sign.value,
            "moon_house": moon.house.house,
            "moon_sign": moon.sign.sign.value,
            "houses": {str(h): v for h, v in sorted(houses.items())},
            "house_system": self.chart.house_system.value,
        }


class LunarReturnCalculator:
    """月返计算：正向求最近一次月返 + 当前地排盘。"""

    def __init__(self, calculator: NatalChartCalculator | None = None):
        self._calculator = calculator or NatalChartCalculator()

    # -- 核心 -------------------------------------------------------------

    def compute(
        self,
        natal_chart: Chart,
        location: GeoLocation | None = None,
        reference: datetime | None = None,
        house_system: HouseSystem | None = None,
        birth_location: GeoLocation | None = None,
    ) -> LunarReturn:
        """当前生效的月返（参考时刻之前最近一次）。

        默认排盘地点 = 出生地（birth_location）；显式传 location 可改用当前地。
        宫位随地点变，出口带 location_type 标注。
        """
        loc = location or birth_location
        if loc is None:
            raise ValueError("返回盘需排盘地点（默认出生地 birth_location）")

        ref = reference or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        natal_moon_lon = natal_chart.planets[Planet.MOON].ecliptic.longitude % 360.0
        hs = house_system or natal_chart.house_system

        moment = self.find_return_moment(natal_moon_lon, ref)
        next_moment = self.find_next_return(natal_moon_lon, moment)

        ret_person = Person(
            id="lunar_return",
            name="月返",
            birth=BirthData(moment, loc),
            house_system=hs,
        )
        return_chart = self._calculator.compute(ret_person)
        return LunarReturn(
            moment=moment,
            effective_until=next_moment,
            chart=return_chart,
            location_zh=loc.place_name or loc.timezone_name,
            location_type=classify_return_location(birth_location, loc),
        )

    # -- 求根（复用共享 returns.py）-----------------------------------------

    def find_return_moment(
        self, natal_moon_lon: float, before: datetime
    ) -> datetime:
        return find_return_before(_moon_lon, natal_moon_lon, before, scan_days=_MOON_SCAN_DAYS)

    def find_next_return(
        self, natal_moon_lon: float, after: datetime
    ) -> datetime:
        return find_return_after(_moon_lon, natal_moon_lon, after)
