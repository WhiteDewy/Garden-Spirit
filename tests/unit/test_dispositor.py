"""飞星解析黄金测试：宫主星飞入各宫（得吉/受克）。

客户盘（1981-08-20 龙江）：金星6/7/11R飞10 得吉；火星5/8R飞8 受克。
对齐专业解读（docs 内）。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.interpretation import dispositor_interpretations
from domain.astrology.knowledge import load_knowledge
from shared.enums import AspectApplication, AspectType, ChartType, HouseSystem, Planet, PlanetSpeed, Sect, Sign, ZodiacType
from shared.models import (
    Aspect,
    BirthData,
    Chart,
    ChartPlanet,
    EclipticPosition,
    GeoLocation,
    HouseCusp,
    HousePosition,
    Person,
    SignPosition,
)

def _minimal_dispositor_chart() -> Chart:
    """3宫主金星飞5宫：金星处女落陷但有三分/界，用于锁定混合尊贵。"""
    now = datetime.now(timezone.utc)
    return Chart(
        id="dispositor_mix",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            Planet.VENUS: ChartPlanet(
                planet=Planet.VENUS,
                ecliptic=EclipticPosition(longitude=157.5),
                sign=SignPosition(sign=Sign.VIRGO, degree_absolute=157.5, degree_in_sign=7.5),
                house=HousePosition(house=5, cusp_degree=90.0, distance_from_cusp=67.5),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            ),
            Planet.SATURN: ChartPlanet(
                planet=Planet.SATURN,
                ecliptic=EclipticPosition(longitude=247.5),
                sign=SignPosition(sign=Sign.SAGITTARIUS, degree_absolute=247.5, degree_in_sign=7.5),
                house=HousePosition(house=8, cusp_degree=180.0, distance_from_cusp=67.5),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            ),
        },
        aspects=[
            Aspect(
                Planet.VENUS,
                Planet.SATURN,
                AspectType.SQUARE,
                90.0,
                1.0,
                AspectApplication.APPLYING,
            )
        ],
        house_cusps={
            1: HouseCusp(house=1, degree=330.0, sign=Sign.PISCES),
            2: HouseCusp(house=2, degree=0.0, sign=Sign.ARIES),
            3: HouseCusp(house=3, degree=30.0, sign=Sign.TAURUS),
            4: HouseCusp(house=4, degree=60.0, sign=Sign.GEMINI),
            5: HouseCusp(house=5, degree=90.0, sign=Sign.CANCER),
            6: HouseCusp(house=6, degree=120.0, sign=Sign.LEO),
            7: HouseCusp(house=7, degree=150.0, sign=Sign.VIRGO),
            8: HouseCusp(house=8, degree=180.0, sign=Sign.LIBRA),
            9: HouseCusp(house=9, degree=210.0, sign=Sign.SCORPIO),
            10: HouseCusp(house=10, degree=240.0, sign=Sign.SAGITTARIUS),
            11: HouseCusp(house=11, degree=270.0, sign=Sign.CAPRICORN),
            12: HouseCusp(house=12, degree=300.0, sign=Sign.AQUARIUS),
        },
        sect=Sect.DAY,
    )


@pytest.fixture(scope="module")
def chart():
    p = Person(
        id="p_client",
        name="客户",
        gender="女",
        birth=BirthData(
            datetime(1981, 8, 20, 13, 10, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(47.3333, 123.2, timezone_name="Asia/Shanghai", place_name="黑龙江龙江"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


@pytest.fixture(scope="module")
def kb():
    return load_knowledge()


def test_venus_6_7_11_to_10_jin(chart, kb):
    """金星(6R/7R/11R)飞10宫 → 得吉：技能成事业/伴侣合伙/口碑转介绍。"""
    readings = dispositor_interpretations(chart, kb)
    # 6飞10
    r6 = next(r for r in readings if r.from_house == 6 and r.to_house == 10)
    assert r6.lord == Planet.VENUS and r6.quality == "jin"
    # 7飞10
    r7 = next(r for r in readings if r.from_house == 7 and r.to_house == 10)
    assert r7.lord == Planet.VENUS and r7.quality == "jin"
    # 11飞10
    r11 = next(r for r in readings if r.from_house == 11 and r.to_house == 10)
    assert r11.lord == Planet.VENUS and r11.quality == "jin"


def test_mars_5_to_8_ke(chart, kb):
    """火星(落陷)飞8宫 → 受克：虐恋/操控主题。"""
    readings = dispositor_interpretations(chart, kb)
    r = next(r for r in readings if r.from_house == 5 and r.to_house == 8)
    assert r.lord == Planet.MARS and r.quality == "ke"
    assert r.lord.value == "mars"


def test_dispositor_marks_mixed_debility_as_ke(kb):
    """飞星受克消费 assess_planet：金星处女落陷即受克，不能被三分/界净成得吉。"""
    readings = dispositor_interpretations(_minimal_dispositor_chart(), kb, houses=[3])

    assert len(readings) == 1
    r = readings[0]
    assert r.from_house == 3
    assert r.to_house == 5
    assert r.lord == Planet.VENUS
    assert r.quality == "ke"


def test_dispositor_export(chart, kb):
    """出口：to_dict 全 JSON 友好。"""
    readings = dispositor_interpretations(chart, kb)
    assert readings
    d = [r.to_dict() for r in readings]
    json.dumps(d, ensure_ascii=False)
    assert d[0]["from_house"] and d[0]["quality"] in ("jin", "ke")
