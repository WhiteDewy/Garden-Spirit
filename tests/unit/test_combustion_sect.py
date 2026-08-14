"""F3/F4 + 两轴 assess_planet 的单元测试。

- 燃烧/日核/日光下（combustion_state）：17′ 日核 +1.0 / 8.5° 燃烧 -1.0 / 17° 日光下 -0.5。
- 吉凶星昼夜缩放（_benefic_malefic_scale）：吉星得时满额、失时减半；凶星得时减半、失时满额。
- 两轴 assess_planet：本质轴（尊贵）× 境遇轴（燃烧/吉凶星sect/角续果/逆行/日月sect light/相位）各带 pos/neg。
- 四象限判（_verdict_axes）：本质优先，本质中性时境遇兜底。

（得时/失时 F4b 待阶段 1 系数收敛后再接，见 docs/refactor_plan.md §14.1 F4。）
"""

from datetime import datetime, timezone

from domain.astrology.common import (
    _angularity_score,
    _benefic_malefic_scale,
    _sect_light_score,
    assess_planet,
    combustion_state,
    planet_strength,
)
from domain.astrology.knowledge import load_knowledge
from domain.astrology.interpretation.compositor import DomainCompositor
from shared.enums import ChartType, HouseSystem, Planet, PlanetSpeed, Sect, Sign, ZodiacType
from shared.models import (
    Chart,
    ChartPlanet,
    EclipticPosition,
    HousePosition,
    SignPosition,
)


def _make_chart(
    positions: dict[Planet, float],
    sect: Sect = Sect.DAY,
    house: int = 1,
    speed: PlanetSpeed = PlanetSpeed.DIRECT,
) -> Chart:
    planets = {}
    for p, lon in positions.items():
        planets[p] = ChartPlanet(
            planet=p,
            ecliptic=EclipticPosition(longitude=lon),
            sign=SignPosition(
                sign=Sign.ARIES, degree_absolute=lon % 360.0, degree_in_sign=lon % 30.0
            ),
            house=HousePosition(house=house, cusp_degree=0.0, distance_from_cusp=0.0),
            speed=speed,
            speed_deg_per_day=1.0,
        )
    now = datetime.now(timezone.utc)
    return Chart(
        id="t", person_id="p", chart_type=ChartType.NATAL,
        calculated_at_utc=now, julian_day=0.0, epoch_utc=now,
        location="", zodiac=ZodiacType.TROPICAL, house_system=HouseSystem.WHOLE_SIGN,
        planets=planets, sect=sect,
    )


# -- 燃烧/日核 --------------------------------------------------------------

def test_combustion_cazimi():
    """合日 0.2°（<17′）→ 日核 +1.0。"""
    chart = _make_chart({Planet.SUN: 10.0, Planet.MERCURY: 10.2})
    assert combustion_state(chart, Planet.MERCURY) == (1.0, "日核")


def test_combustion_combust():
    """合日 5°（17′~8.5°）→ 燃烧 -1.0。"""
    chart = _make_chart({Planet.SUN: 10.0, Planet.VENUS: 15.0})
    assert combustion_state(chart, Planet.VENUS) == (-1.0, "燃烧")


def test_combustion_under_beams():
    """合日 10°（8.5°~17°）→ 日光下 -0.5。"""
    chart = _make_chart({Planet.SUN: 10.0, Planet.MARS: 20.0})
    assert combustion_state(chart, Planet.MARS) == (-0.5, "日光下")


def test_combustion_none():
    """合日 20°（>17°）→ 无。"""
    chart = _make_chart({Planet.SUN: 10.0, Planet.JUPITER: 30.0})
    assert combustion_state(chart, Planet.JUPITER) == (0.0, None)


def test_combustion_skips_sun_and_outers():
    """太阳本身与三王星/虚点不参与燃烧判定。"""
    chart = _make_chart({Planet.SUN: 10.0, Planet.NEPTUNE: 15.0, Planet.SATURN: 15.0})
    assert combustion_state(chart, Planet.SUN) == (0.0, None)
    assert combustion_state(chart, Planet.NEPTUNE) == (0.0, None)
    # 土星是七曜 → 参与（5° 燃烧）
    assert combustion_state(chart, Planet.SATURN) == (-1.0, "燃烧")


# -- 吉凶星昼夜缩放 ---------------------------------------------------------

def test_benefic_malefic_scale():
    # 吉星得时满额、失时减半
    assert _benefic_malefic_scale(Planet.JUPITER, Sect.DAY) == 1.0
    assert _benefic_malefic_scale(Planet.JUPITER, Sect.NIGHT) == 0.5
    assert _benefic_malefic_scale(Planet.VENUS, Sect.NIGHT) == 1.0
    assert _benefic_malefic_scale(Planet.VENUS, Sect.DAY) == 0.5
    # 凶星得时减半、失时满额
    assert _benefic_malefic_scale(Planet.MARS, Sect.NIGHT) == 0.5
    assert _benefic_malefic_scale(Planet.MARS, Sect.DAY) == 1.0
    assert _benefic_malefic_scale(Planet.SATURN, Sect.DAY) == 0.5
    assert _benefic_malefic_scale(Planet.SATURN, Sect.NIGHT) == 1.0
    # 非吉凶星 / 无 sect → 1.0
    assert _benefic_malefic_scale(Planet.SUN, Sect.DAY) == 1.0
    assert _benefic_malefic_scale(Planet.MARS, None) == 1.0


# -- 日月 sect light --------------------------------------------------------

def test_sect_light_score():
    assert _sect_light_score(_make_chart({Planet.SUN: 0.0}, Sect.DAY), Planet.SUN) == 0.5
    assert _sect_light_score(_make_chart({Planet.MOON: 0.0}, Sect.DAY), Planet.MOON) == -0.5
    assert _sect_light_score(_make_chart({Planet.SUN: 0.0}, Sect.NIGHT), Planet.SUN) == -0.5
    assert _sect_light_score(_make_chart({Planet.MOON: 0.0}, Sect.NIGHT), Planet.MOON) == 0.5
    # 非日月不计
    assert _sect_light_score(_make_chart({Planet.MARS: 0.0}, Sect.DAY), Planet.MARS) == 0.0


# -- 角续果 ----------------------------------------------------------------

def test_angularity_score():
    kb = load_knowledge()
    # 角宫（1宫）→ +1.0
    assert _angularity_score(_make_chart({Planet.MARS: 10.0}, house=1), kb, Planet.MARS) == 1.0
    # 续宫（2宫）→ +0.5
    assert _angularity_score(_make_chart({Planet.MARS: 10.0}, house=2), kb, Planet.MARS) == 0.5
    # 果宫（3宫）→ 0
    assert _angularity_score(_make_chart({Planet.MARS: 10.0}, house=3), kb, Planet.MARS) == 0.0


# -- 两轴 assess_planet -----------------------------------------------------

def _summer_chart() -> Chart:
    from datetime import datetime as _dt
    import zoneinfo
    from domain.astrology.calculation import NatalChartCalculator
    from shared.models import BirthData, GeoLocation, Person

    p = Person(
        id="p_assess", name="夏天", gender="女",
        birth=BirthData(
            _dt(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


def test_assess_planet_two_axes_separate():
    """本质轴（尊贵）与境遇轴（燃烧/角续果/相位）各带 pos/neg，不抵消。"""
    chart = _summer_chart()
    kb = load_knowledge()
    sat = assess_planet(chart, kb, Planet.SATURN)
    assert sat.essential_pos > 0                 # 土星庙（本质强）
    merc = assess_planet(chart, kb, Planet.MERCURY)
    assert merc.accidental_neg > 0               # 水星日光下 + 刑（境遇弱）
    assert merc.essential_pos > 0                # 水星界（本质有吉）——与境遇弱分开，不抵消
    assert "日光下" in "".join(merc.accidental_ev)


def test_assess_planet_retrograde_wired():
    """逆行进境遇轴凶轨。"""
    kb = load_knowledge()
    chart = _make_chart({Planet.MARS: 10.0}, speed=PlanetSpeed.RETROGRADE)
    a = assess_planet(chart, kb, Planet.MARS)
    assert a.accidental_neg > 0
    assert any("逆行" in ev for ev in a.accidental_ev)


# -- 四象限判 --------------------------------------------------------------

def test_verdict_axes_essential_first():
    """本质（尊贵）优先：落陷即 weak，即便境遇/关系尚可；本质中性时境遇+关系兜底。"""
    comp = DomainCompositor(load_knowledge())
    # 本质弱（落陷 net -1.75）+ 境遇顺（+1.4）→ 仍 weak
    assert comp._verdict_axes(-1.75, 1.4, 0.0) == "weak"
    # 本质强（+1.75）+ 境遇逆（-1.4）→ 仍 strong
    assert comp._verdict_axes(1.75, -1.4, 0.0) == "strong"
    # 本质中性 + 境遇强 → strong（境遇兜底）
    assert comp._verdict_axes(0.0, 1.5, 0.0) == "strong"
    # 本质中性 + 境遇弱 → weak
    assert comp._verdict_axes(0.0, -1.5, 0.0) == "weak"
    # 本质中性 + 关系受克 → weak（关系轴也兜底）
    assert comp._verdict_axes(0.0, 0.0, -1.5) == "weak"
    # 双中性 → mixed
    assert comp._verdict_axes(0.0, 0.0, 0.0) == "mixed"


def test_assess_planet_excludes_minor_aspects():
    """次要相位（半刑/五相/梅花/八分相）不进关系轴，主相位（刑/六合）保留。"""
    chart = _summer_chart()
    kb = load_knowledge()
    a = assess_planet(chart, kb, Planet.MERCURY)
    rel = "".join(a.relational_ev)
    assert not any(w in rel for w in ("五相", "半刑", "梅花", "八分相"))
    assert any("刑" in ev for ev in a.relational_ev)      # 刑天王/海王（主相位）仍在
    assert any("六合" in ev for ev in a.relational_ev)    # 六合火星（主相位）仍在


def test_assess_planet_wires_reception_helpers():
    """互溶/接纳进关系轴正向（帮手星）：夏天盘火星↔水星互溶。"""
    chart = _summer_chart()
    kb = load_knowledge()
    a = assess_planet(chart, kb, Planet.MARS)
    assert any("互溶" in ev for ev in a.relational_ev)
    assert a.relational_pos > 0    # 互溶是正向分量


def test_reception_excludes_outer_planets():
    """三王星不参与互溶接纳（只做关联相位，不做结构判断）。"""
    chart = _summer_chart()
    kb = load_knowledge()
    a = assess_planet(chart, kb, Planet.URANUS)
    # 天王星：无互溶（↔）、无真接纳（"接纳"只以"未接纳"相位标签出现）
    assert not any("↔" in ev for ev in a.relational_ev)
    assert not any("接纳" in ev and "未接纳" not in ev for ev in a.relational_ev)
    # 但关系轴相位仍在（三王星做关联影响）
    assert any("刑" in ev or "冲" in ev or "六合" in ev for ev in a.relational_ev)


def test_helpers_of_public_method():
    """helpers_of 公共方法直接返回帮手星：火星↔水星互溶、三王星无帮手。"""
    from domain.astrology.interpretation.synapsis import ConnectionClassifier
    chart = _summer_chart()
    kb = load_knowledge()
    clf = ConnectionClassifier(kb)
    mars_helpers = clf.helpers_of(chart, Planet.MARS)
    assert any(p == Planet.MERCURY and k == "mutual" for p, k in mars_helpers)
    # 三王星无帮手（excluded）
    assert clf.helpers_of(chart, Planet.URANUS) == []


def test_assess_planet_memoized():
    """预计算查表：同一颗星第二次调用命中缓存（返回同一对象，不重算）。"""
    chart = _summer_chart()
    kb = load_knowledge()
    a1 = assess_planet(chart, kb, Planet.MARS)
    a2 = assess_planet(chart, kb, Planet.MARS)
    assert a1 is a2                 # 缓存命中，同一对象
    assert len(chart.planet_assessments) == 1  # 只算了一次


# -- planet_strength 接线 ---------------------------------------------------

def test_planet_strength_wires_combustion():
    """planet_strength 应产出燃烧证据（夏天盘：水星距日 16.61° → 日光下）。"""
    chart = _summer_chart()
    kb = load_knowledge()
    _pos, _neg, merc_ev = planet_strength(chart, kb, Planet.MERCURY)
    assert any("日光下" in ev for ev in merc_ev)
