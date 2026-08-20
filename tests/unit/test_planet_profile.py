"""行星档案黄金测试：每颗星的单点配置（落座/落宫/尊贵/支持者/破坏者/掌宫）。

夏天盘（1991-03-21 山西陵川）：验证各星档案的确定性输出。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.interpretation import (
    PlanetProfile,
    read_all_planets,
    read_planet,
)
from domain.astrology.interpretation.planet_profile import pick_for_theme
from domain.astrology.knowledge import load_knowledge
from shared.enums import ChartType, HouseSystem, Planet, PlanetSpeed, Sect, Sign, ZodiacType
from shared.models import (
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


def _minimal_chart_for_planet(planet: Planet, longitude: float, sign: Sign, degree_in_sign: float) -> Chart:
    now = datetime.now(timezone.utc)
    return Chart(
        id="profile_mix",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            planet: ChartPlanet(
                planet=planet,
                ecliptic=EclipticPosition(longitude=longitude),
                sign=SignPosition(sign=sign, degree_absolute=longitude, degree_in_sign=degree_in_sign),
                house=HousePosition(house=1, cusp_degree=0.0, distance_from_cusp=0.0),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            )
        },
        house_cusps={
            h: HouseCusp(house=h, degree=float((h - 1) * 30), sign=list(Sign)[h - 1])
            for h in range(1, 13)
        },
        sect=Sect.DAY,
    )


@pytest.fixture(scope="module")
def chart():
    p = Person(
        id="x",
        name="夏天",
        gender="女",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西省陵川县"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


@pytest.fixture(scope="module")
def kb():
    return load_knowledge()


# -- 全量档案 ----------------------------------------------------------

def test_read_all_planets_10(chart, kb):
    """10颗主星全量产出。"""
    profiles = read_all_planets(chart, kb)
    assert len(profiles) == 10
    for p in profiles:
        assert p.sign_style, f"{p.planet}: sign_style 为空"
        assert p.behavior_style, f"{p.planet}: behavior_style 为空"
        assert p.house_name, f"{p.planet}: house_name 为空"
        assert p.dignity_label, f"{p.planet}: dignity_label 为空"


def test_venus_profile(chart, kb):
    """金星金牛12宫入庙：落座风格=物质滋养，尊贵=入庙。"""
    v = read_planet(chart, kb, Planet.VENUS)
    assert "物质滋养" in v.sign_style
    assert v.house_name == "落12宫"
    assert v.dignity_label == "入庙"
    assert v.dignity_score >= 5
    # 掌宫（夏天盘6宫头天秤→金星主 + 截夺天蝎）
    assert 6 in v.rulings


def test_moon_profile(chart, kb):
    """月亮双子1宫游走：落座风格=需要被理解回应。"""
    m = read_planet(chart, kb, Planet.MOON)
    assert "交流" in m.sign_style or "说" in m.sign_style or "理解" in m.sign_style
    assert m.house_name == "落1宫"
    assert m.dignity_label == "游走"


def test_mars_profile(chart, kb):
    """火星双子1宫：有界支撑，但不能误标成入旺；破坏者不含次要相位。"""
    ma = read_planet(chart, kb, Planet.MARS)
    assert ma.house_name == "落1宫"
    assert 6 in ma.rulings
    assert 12 in ma.rulings
    assert "界" in ma.dignity_label
    assert not ma.dignity_label.startswith("入旺")
    assert "入旺" not in ma.dignity_label
    # 火星的破坏者：火刑日（磨合）、火冲莉莉丝（外部压力）
    assert any("太阳" in u and "刑" in u for u in ma.underminers)
    # 不应含半刑/八分/梅花
    assert not any("半刑" in u or "八分" in u or "梅花" in u for u in ma.underminers)


def test_moon_supporters(chart, kb):
    """月亮的支持者：六合日、六合木（有接纳）、三合土。"""
    m = read_planet(chart, kb, Planet.MOON)
    assert any("木星" in s and "六合" in s for s in m.supporters)
    assert any("土星" in s and "三合" in s for s in m.supporters)


# -- 尊贵标签 ----------------------------------------------------------

def test_dignity_labels_distinct(chart, kb):
    """不同星的尊贵标签不全都一样。"""
    profiles = read_all_planets(chart, kb)
    labels = {p.planet: p.dignity_label for p in profiles}
    # 金星入庙、月亮游走——至少有两种标签
    assert len(set(labels.values())) >= 2


def test_planet_profile_keeps_mixed_dignity_visible(kb):
    """星档案消费 assess_planet：火星天秤失势，但仍保留埃及界支撑，不净成普通游走。"""
    chart = _minimal_chart_for_planet(Planet.MARS, 207.0, Sign.LIBRA, 27.0)

    mars = read_planet(chart, kb, Planet.MARS)

    assert mars.dignity_score < 0
    assert mars.dignity_label.startswith("失势")
    assert "支撑" in mars.dignity_label


def test_planet_profile_positive_net_fall_still_reads_as_limited(kb):
    """金星处女落陷 + 三分/界/面净分为正，也不能在星档案显示成纯入旺。"""
    chart = _minimal_chart_for_planet(Planet.VENUS, 160.5, Sign.VIRGO, 10.5)

    venus = read_planet(chart, kb, Planet.VENUS)

    assert venus.dignity_score < 0
    assert venus.dignity_label.startswith("落陷")
    assert "支撑" in venus.dignity_label
    assert "受限" in venus.dignity_label
    assert not venus.dignity_label.startswith("入旺")
def test_planet_profile_term_only_is_minor_support(kb):
    """小尊贵只显示有限支撑：火星双子23°在界，不是入旺/曜升。"""
    chart = _minimal_chart_for_planet(Planet.MARS, 83.28688576501335, Sign.GEMINI, 23.286885765013352)

    mars = read_planet(chart, kb, Planet.MARS)

    assert mars.dignity_score == 2
    assert mars.dignity_label == "在界"
    assert "入旺" not in mars.dignity_label


# -- 星座行为方式 --------------------------------------------------------

def test_sign_behavior_style_loaded(kb):
    """signs.yaml 的星座行为方式被 loader 暴露。"""
    from shared.enums import Sign

    assert "先冲再说" in kb.sign(Sign.ARIES).behavior_style
    assert "边说边想" in kb.sign(Sign.GEMINI).behavior_style


# -- 落座风格差异化 ----------------------------------------------------

def test_sign_style_differs(chart, kb):
    """金星金牛 ≠ 火星双子 ≠ 月亮双子：落座风格不同。"""
    v = read_planet(chart, kb, Planet.VENUS).sign_style
    ma = read_planet(chart, kb, Planet.MARS).sign_style
    m = read_planet(chart, kb, Planet.MOON).sign_style
    assert v != ma
    assert v != m


# -- 主题抓取 ----------------------------------------------------------

def test_pick_for_theme_relationship(chart, kb):
    """感情主题抓取金火月+日月土。"""
    profiles = read_all_planets(chart, kb)
    love = pick_for_theme(profiles, (Planet.VENUS, Planet.MARS, Planet.MOON))
    assert {p.planet for p in love} == {Planet.VENUS, Planet.MARS, Planet.MOON}


def test_pick_for_theme_career(chart, kb):
    """事业主题抓取日木土。"""
    profiles = read_all_planets(chart, kb)
    career = pick_for_theme(profiles, (Planet.SUN, Planet.JUPITER, Planet.SATURN))
    assert {p.planet for p in career} == {Planet.SUN, Planet.JUPITER, Planet.SATURN}


# -- 出口 --------------------------------------------------------------

def test_to_dict_json(chart, kb):
    """to_dict 全 JSON 友好。"""
    profiles = read_all_planets(chart, kb)
    data = [p.to_dict() for p in profiles]
    json.dumps(data, ensure_ascii=False)
    first = data[0]
    for key in ("planet", "sign_style", "behavior_style", "house_name", "house_domain",
                "dignity_label", "dignity_score", "supporters",
                "underminers", "rulings", "ruling_labels"):
        assert key in first


def test_house_domain_from_planet_in_house(chart, kb):
    """落宫领域来自 planet_in_house.yaml（金星12宫有 base 文案）。"""
    v = read_planet(chart, kb, Planet.VENUS)
    assert v.house_domain  # 非空
    assert len(v.house_domain) > 5
