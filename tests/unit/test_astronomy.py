"""Phase 2 验证：知识库 + 本命盘黄金测试。

用 Lady Gaga 的公开出生数据（1986-03-28 05:30, New York）做回归基线。
参考：astro.com 公开数据（太阳白羊、月亮天蝎、上升双鱼、火星摩羯曜升等）。
"""

from datetime import datetime
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from shared.enums import DignityState, Planet, Sect, Sign
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def gaga_chart():
    person = Person(
        id="gaga",
        name="Lady Gaga",
        birth=BirthData(
            datetime(1986, 3, 28, 5, 30, tzinfo=zoneinfo.ZoneInfo("America/New_York")),
            GeoLocation(
                40.7128, -74.0060,
                timezone_name="America/New_York",
                place_name="New York",
            ),
        ),
    )
    return NatalChartCalculator().compute(person)


def test_knowledge_base_loads():
    kb = load_knowledge()
    assert len(kb.planets) >= 14
    assert len(kb.signs) == 12
    assert len(kb.houses) == 12
    assert len(kb.aspects) >= 10
    assert kb.dignity is not None
    assert kb.reception is not None
    assert not hasattr(kb, "house_nature")
    assert len(kb.house_derived) == 12
    assert len(kb.house_derived[7]) == 12
    assert "婚姻本身" in kb.house_derived[7][7]


def test_golden_sun_sign(gaga_chart):
    """太阳白羊 7.45°，曜升。"""
    sun = gaga_chart.planets[Planet.SUN]
    assert sun.sign.sign == Sign.ARIES
    assert 7.0 < sun.sign.degree_in_sign < 8.0
    assert DignityState.EXALTATION in [d.dignity_state for d in gaga_chart.dignities[Planet.SUN]]


def test_golden_moon_sign(gaga_chart):
    """月亮天蝎，落陷。"""
    moon = gaga_chart.planets[Planet.MOON]
    assert moon.sign.sign == Sign.SCORPIO
    assert DignityState.FALL in [d.dignity_state for d in gaga_chart.dignities[Planet.MOON]]


def test_golden_ascendant(gaga_chart):
    """上升双鱼。"""
    assert gaga_chart.ascendant is not None
    assert gaga_chart.ascendant.sign == Sign.PISCES


def test_golden_mars_exalted(gaga_chart):
    """火星摩羯曜升，落十宫（事业）。"""
    mars = gaga_chart.planets[Planet.MARS]
    assert mars.sign.sign == Sign.CAPRICORN
    assert DignityState.EXALTATION in [d.dignity_state for d in gaga_chart.dignities[Planet.MARS]]
    assert mars.house.house == 10


def test_golden_jupiter_domicile(gaga_chart):
    """木星双鱼入庙。"""
    jupiter = gaga_chart.planets[Planet.JUPITER]
    assert jupiter.sign.sign == Sign.PISCES
    assert DignityState.DOMICILE in [d.dignity_state for d in gaga_chart.dignities[Planet.JUPITER]]


def test_mercury_retrograde(gaga_chart):
    """水星逆行。"""
    mercury = gaga_chart.planets[Planet.MERCURY]
    assert mercury.speed.value == "retrograde"


def test_south_node_derived(gaga_chart):
    """南交点 = 北交点 + 180°。"""
    north = gaga_chart.planets[Planet.NORTH_NODE].ecliptic.longitude
    south = gaga_chart.planets[Planet.SOUTH_NODE].ecliptic.longitude
    assert abs(((south - north) % 360) - 180) < 0.1


def test_aspects_present(gaga_chart):
    """应有本命相位。"""
    assert len(gaga_chart.aspects) > 20
    kinds = {a.aspect_type for a in gaga_chart.aspects}
    assert "conjunction" in kinds or "square" in kinds or "trine" in kinds


def test_lots_present(gaga_chart):
    """福点存在且落座合法。"""
    assert len(gaga_chart.lots) >= 1
    assert all(0 <= lot.degree < 360 for lot in gaga_chart.lots)
