"""本命盘计算器。

将 Swiss Ephemeris 原始输出 + 知识库，转化为统一的 Chart 模型。
这是占星层唯一允许调用 foundation/astronomy 的地方。
"""

from __future__ import annotations

from datetime import timezone

from foundation.astronomy import ephemeris as swe_wrap
from foundation.astronomy.timezone import to_utc
from foundation.config import EphemerisConfig
from foundation.logger import get_logger
from foundation.utils import new_id, utc_now
from shared.constants import SE_PLANET_IDS
from shared.enums import (
    AspectApplication,
    AspectType,
    ChartType,
    HouseSystem,
    Planet,
    PlanetSpeed,
    Sect,
    Sign,
)
from shared.models import (
    Aspect,
    Chart,
    ChartAcceptance,
    ChartPlanet,
    ChartReception,
    EclipticPosition,
    EssentialDignity,
    HouseCusp,
    HousePosition,
    Lot,
    Person,
    SignPosition,
)

from domain.astrology.knowledge.dignity import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase, load_knowledge
from domain.astrology.knowledge.reception import ReceptionEngine
from domain.astrology.knowledge.sect import SectEngine

logger = get_logger("astrology.calculation")

# 参与相位计算的天体（含节点/凯龙/莉莉丝，容许度更小由 aspects.yaml 控制）
_ASPECT_BODIES = list(SE_PLANET_IDS.keys())


def _chart_reception(r) -> ChartReception:
    """ReceptionEngine 输出 → 可序列化的 Chart 快照。"""
    return ChartReception(
        planet_a=r.planet_a,
        planet_b=r.planet_b,
        dignities_of_a_at_b=tuple(r.dignities_of_a_at_b),
        dignities_of_b_at_a=tuple(r.dignities_of_b_at_a),
        dignity_type=r.dignity_type,
        score=r.score,
        aspect_type=r.aspect_type,
        aspect_nature=r.aspect_nature,
        description_zh=r.description_zh,
    )


def _chart_acceptance(a) -> ChartAcceptance:
    """AcceptanceEngine 输出 → 可序列化的 Chart 快照。"""
    return ChartAcceptance(
        acceptor=a.acceptor,
        accepted=a.accepted,
        dignities=tuple(a.dignities),
        dignity_type=a.dignity_type,
        score=a.score,
        aspect_type=a.aspect_type,
        aspect_nature=a.aspect_nature,
        description_zh=a.description_zh,
    )


class NatalChartCalculator:
    """计算本命盘 Chart。"""

    def __init__(
        self,
        config: EphemerisConfig | None = None,
        kb: KnowledgeBase | None = None,
    ):
        self.config = config or EphemerisConfig()
        self.kb = kb or load_knowledge()
        self.dignity_engine = DignityEngine(self.kb)
        self.reception_engine = ReceptionEngine(self.kb, self.dignity_engine)
        self.sect_engine = SectEngine()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def compute(
        self, person: Person, house_system: HouseSystem | None = None
    ) -> Chart:
        """根据 Person 出生数据计算本命盘。

        宫位制解析优先级：
          1. house_system 参数（强制——合盘需双方一致时用）
          2. person.house_system（个人偏好）
          3. config.default_house_system（全局默认）
        """
        house_system = (
            house_system
            or person.house_system
            or self.config.default_house_system
        )

        utc_dt = self._resolve_utc(person)
        jd = swe_wrap.to_julian_day(utc_dt)
        lat = person.birth.location.latitude
        lon = person.birth.location.longitude

        # 1. 行星位置（Chiron 需要完整瑞士星历，Moshier 下跳过）
        bodies = [
            p for p in SE_PLANET_IDS
            if p != Planet.CHIRON or swe_wrap.ephemeris_available()
        ]
        positions = {p: swe_wrap.planet_full(jd, p) for p in bodies}

        # 2. 宫位
        house_data = swe_wrap.house_cusps(jd, lat, lon, house_system.value)
        cusps = house_data["cusps"]

        # 3. 行星落宫 + 星座
        planet_entries: dict[Planet, ChartPlanet] = {}
        for planet, data in positions.items():
            planet_entries[planet] = self._chart_planet(planet, data, cusps)

        # 4. 相位表
        aspects = self._compute_aspects(jd, planet_entries)

        # 5. 尊贵 / 互容 / sect
        sun_house = planet_entries[Planet.SUN].house.house
        sect = self.sect_engine.compute(sun_house)
        dignities = self._compute_dignities(planet_entries, sect)
        receptions = self.reception_engine.detect(
            {p: (pe.sign.sign, pe.sign.degree_in_sign) for p, pe in planet_entries.items()},
            sect=sect,
            aspects=aspects,
        )
        acceptances = self.reception_engine.detect_acceptance(
            {p: (pe.sign.sign, pe.sign.degree_in_sign) for p, pe in planet_entries.items()},
            aspects,
            sect=sect,
        )

        # 6. 特殊点（福点等）
        lots = self._compute_lots(planet_entries, house_data["ascendant"], cusps, sect)

        # 7. 月相
        moon_phase = swe_wrap.moon_phase_angle(jd) / 360.0

        chart = Chart(
            id=new_id("chart"),
            person_id=person.id,
            chart_type=ChartType.NATAL,
            calculated_at_utc=utc_now(),
            julian_day=jd,
            epoch_utc=utc_dt,
            location=person.birth.location.place_name or person.birth.location.timezone_name,
            zodiac=self.config.zodiac,
            house_system=house_system,
            planets=planet_entries,
            house_cusps={
                h: HouseCusp(house=h, degree=cusps[h], sign=self._sign_for(cusps[h]))
                for h in range(1, 13)
            },
            ascendant=self._sign_position(house_data["ascendant"]),
            midheaven=self._sign_position(house_data["midheaven"]),
            aspects=aspects,
            dignities=dignities,
            receptions=[_chart_reception(r) for r in receptions],
            acceptances=[_chart_acceptance(a) for a in acceptances],
            lots=lots,
            sect=sect,
            moon_phase=moon_phase,
        )
        logger.info(
            "本命盘计算完成: %s, 太阳落%s %d宫, %d个相位, %d组互容",
            person.id,
            planet_entries[Planet.SUN].sign.sign.value,
            planet_entries[Planet.SUN].house.house,
            len(aspects),
            len(receptions),
        )
        return chart

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_utc(person: Person) -> "datetime":
        """出生本地时间 → UTC（含时区/夏令时处理）。"""
        from datetime import datetime  # noqa: F401

        bd = person.birth
        if bd.datetime_utc.tzinfo is not None:
            return bd.datetime_utc.astimezone(timezone.utc).replace(tzinfo=None)
        return to_utc(bd.datetime_utc, bd.location.timezone_name)

    def _sign_for(self, longitude: float) -> Sign:
        idx = int(longitude // 30.0) % 12
        return list(Sign)[idx]

    def _sign_position(self, longitude: float) -> SignPosition:
        sign = self._sign_for(longitude)
        return SignPosition(
            sign=sign,
            degree_absolute=longitude % 360.0,
            degree_in_sign=longitude % 30.0,
        )

    def _chart_planet(
        self, planet: Planet, data: dict, cusps: dict[int, float]
    ) -> ChartPlanet:
        lon = data["longitude"]
        sign = self._sign_for(lon)
        house = self._assign_house(lon, cusps)
        # NOTE: combust/cazimi/under beams 由 indicators 用黄经差值计算，
        # 不在此处判断（保持计算层纯机械）。

        return ChartPlanet(
            planet=planet,
            ecliptic=EclipticPosition(
                longitude=lon,
                latitude=data["latitude"],
                declination=data["declination"],
                right_ascension=data["right_ascension"],
                distance_au=data["distance_au"],
            ),
            sign=SignPosition(
                sign=sign,
                degree_absolute=lon % 360.0,
                degree_in_sign=lon % 30.0,
            ),
            house=HousePosition(
                house=house,
                cusp_degree=cusps[house],
                distance_from_cusp=(lon % 360.0 - cusps[house]) % 360.0,
            ),
            speed=data["speed_category"],
            speed_deg_per_day=data["speed_deg_per_day"],
        )

    @staticmethod
    def _assign_house(longitude: float, cusps: dict[int, float]) -> int:
        """黄经 → 宫位（处理 0/360 回绕）。"""
        cs = [cusps[i] % 360.0 for i in range(1, 13)]
        for i in range(12):
            a = cs[i]
            b = cs[(i + 1) % 12]
            if b < a:
                b += 360.0
            pos = longitude if longitude >= a else longitude + 360.0
            if a <= pos < b:
                return i + 1
        return 12

    # ------------------------------------------------------------------
    # 相位
    # ------------------------------------------------------------------

    def _compute_aspects(
        self, jd: float, planets: dict[Planet, ChartPlanet]
    ) -> list[Aspect]:
        aspects: list[Aspect] = []
        for i, a in enumerate(_ASPECT_BODIES):
            for b in _ASPECT_BODIES[i + 1:]:
                if a not in planets or b not in planets:
                    continue
                aspects.extend(self._pair_aspects(jd, a, b, planets))
        return aspects

    def _pair_aspects(
        self,
        jd: float,
        a: Planet,
        b: Planet,
        planets: dict[Planet, ChartPlanet],
    ) -> list[Aspect]:
        pa, pb = planets[a], planets[b]
        lon_a, lon_b = pa.ecliptic.longitude, pb.ecliptic.longitude
        speed_a, speed_b = pa.speed_deg_per_day, pb.speed_deg_per_day

        result: list[Aspect] = []
        for aspect_type, info in self.kb.aspects.items():
            orb = info.orb
            if a in (Planet.SUN, Planet.MOON) or b in (Planet.SUN, Planet.MOON):
                orb += 2.0
            sep = abs(((lon_a - lon_b + 540.0) % 360.0) - 180.0)
            if abs(sep - info.angle) <= orb:
                result.append(
                    Aspect(
                        body1=a,
                        body2=b,
                        aspect_type=aspect_type,
                        exact_angle=info.angle,
                        orb=abs(sep - info.angle),
                        application=self._application_state(
                            lon_a, lon_b, speed_a, speed_b, info.angle
                        ),
                    )
                )
        return result

    @staticmethod
    def _application_state(
        lon_a: float, lon_b: float, speed_a: float, speed_b: float, aspect_angle: float
    ) -> AspectApplication:
        """判断入相/出相：轻微推进时间比较容许度变化。"""
        dt = 0.5  # 天
        sep0 = abs(((lon_a - lon_b + 540.0) % 360.0) - 180.0)
        sep1 = abs(
            (((lon_a + speed_a * dt) - (lon_b + speed_b * dt) + 540.0) % 360.0) - 180.0
        )
        orb0, orb1 = abs(sep0 - aspect_angle), abs(sep1 - aspect_angle)
        if orb1 < orb0 - 0.001:
            return AspectApplication.APPLYING
        if orb1 > orb0 + 0.001:
            return AspectApplication.SEPARATING
        return AspectApplication.EXACT

    # ------------------------------------------------------------------
    # 尊贵 / 特殊点
    # ------------------------------------------------------------------

    def _compute_dignities(
        self, planets: dict[Planet, ChartPlanet], sect: Sect
    ) -> dict[Planet, list[EssentialDignity]]:
        result: dict[Planet, list[EssentialDignity]] = {}
        for planet, cp in planets.items():
            states, _total = self.dignity_engine.compute(
                planet, cp.sign.sign, cp.sign.degree_in_sign, sect
            )
            result[planet] = [
                EssentialDignity(
                    planet=planet,
                    sign=cp.sign.sign,
                    dignity_state=state,
                    score=self.dignity_engine.score(state),
                )
                for state in states
            ]
        return result

    def _compute_lots(
        self,
        planets: dict[Planet, ChartPlanet],
        ascendant: float,
        cusps: dict[int, float],
        sect: Sect,
    ) -> list[Lot]:
        """福点（昼: Asc+Moon-Sun；夜: Asc+Sun-Moon）+ 精神点。"""
        if Planet.SUN not in planets or Planet.MOON not in planets:
            return []
        sun_lon = planets[Planet.SUN].ecliptic.longitude
        moon_lon = planets[Planet.MOON].ecliptic.longitude

        if sect == Sect.DAY:
            fortune = (ascendant + moon_lon - sun_lon) % 360.0
            spirit = (ascendant + sun_lon - moon_lon) % 360.0
        else:
            fortune = (ascendant + sun_lon - moon_lon) % 360.0
            spirit = (ascendant + moon_lon - sun_lon) % 360.0

        lots: list[Lot] = []
        for name, lon in (("Fortune", fortune), ("Spirit", spirit)):
            lots.append(
                Lot(
                    name=name,
                    formula="Asc+Moon-Sun" if name == "Fortune" else "Asc+Sun-Moon",
                    degree=lon,
                    sign=self._sign_for(lon),
                    house=self._assign_house(lon, cusps),
                )
            )
        return lots
