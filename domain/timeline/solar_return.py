"""日返（Solar Return）计算器。

日返 = 太阳回到本命太阳黄经的时刻起的盘，管一整年（生日→下一生日）。
与月返同构：正向求参考时刻之前最近一次日返 + 当前所在地排盘。
确定性、无 LLM；结果可 to_dict() 序列化（出口，供 app 消费）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from foundation.astronomy.ephemeris import planet_longitude, to_julian_day
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, Chart, GeoLocation, Person

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline.returns import classify_return_location, find_return_after, find_return_before

# 太阳每年回归一次；扫描窗口需覆盖 >1 年
_SOLAR_SCAN_DAYS = 400


def _sun_lon(dt: datetime) -> float:
    return planet_longitude(to_julian_day(dt), Planet.SUN)


@dataclass
class SolarReturn:
    """一次日返（管一整年）。"""

    moment: datetime             # 日返时刻（UTC）
    effective_until: datetime    # 下次日返（生效截止）
    chart: Chart                 # 日返盘
    location_zh: str = ""
    location_type: str = "current_place"   # birth_place / current_place

    def to_dict(self) -> dict:
        """出口：JSON 友好的关键点（供星灵 app 消费）。"""
        planets = self.chart.planets
        sun = planets[Planet.SUN]
        moon = planets[Planet.MOON]
        houses: dict[int, list[str]] = {h: [] for h in range(1, 13)}
        for pl, cp in planets.items():
            if pl == Planet.SOUTH_NODE:
                continue
            houses.setdefault(cp.house.house, []).append(pl.value)
        return {
            "type": "solar_return",
            "moment": self.moment.isoformat(),
            "effective_until": self.effective_until.isoformat(),
            "location": self.location_zh,
            "location_type": self.location_type,
            "ascendant": f"{self.chart.ascendant.sign.value} {self.chart.ascendant.degree_in_sign:.1f}",
            "ascendant_sign": self.chart.ascendant.sign.value,
            "midheaven_sign": self.chart.midheaven.sign.value,
            "sun_house": sun.house.house,
            "sun_sign": sun.sign.sign.value,
            "moon_house": moon.house.house,
            "moon_sign": moon.sign.sign.value,
            "houses": {str(h): v for h, v in sorted(houses.items())},
            "house_system": self.chart.house_system.value,
        }


class SolarReturnCalculator:
    """日返计算：正向求最近一次日返 + 当前地排盘。"""

    def __init__(self, calculator: NatalChartCalculator | None = None):
        self._calculator = calculator or NatalChartCalculator()

    def compute(
        self,
        natal_chart: Chart,
        location: GeoLocation | None = None,
        reference: datetime | None = None,
        house_system: HouseSystem | None = None,
        birth_location: GeoLocation | None = None,
    ) -> SolarReturn:
        """当前生效的日返（参考时刻之前最近一次，管一整年）。

        默认排盘地点 = 出生地（birth_location）；显式传 location 可改用当前地。
        宫位随地点变，出口带 location_type 标注。
        """
        loc = location or birth_location
        if loc is None:
            raise ValueError("返回盘需排盘地点（默认出生地 birth_location）")

        ref = reference or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        natal_sun_lon = natal_chart.planets[Planet.SUN].ecliptic.longitude % 360.0
        hs = house_system or natal_chart.house_system

        moment = find_return_before(_sun_lon, natal_sun_lon, ref, scan_days=_SOLAR_SCAN_DAYS)
        next_moment = find_return_after(_sun_lon, natal_sun_lon, moment, scan_days=370)

        ret_person = Person(
            id="solar_return",
            name="日返",
            birth=BirthData(moment, loc),
            house_system=hs,
        )
        return_chart = self._calculator.compute(ret_person)
        return SolarReturn(
            moment=moment,
            effective_until=next_moment,
            chart=return_chart,
            location_zh=loc.place_name or loc.timezone_name,
            location_type=classify_return_location(birth_location, loc),
        )
