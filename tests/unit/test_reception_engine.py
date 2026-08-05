"""ReceptionEngine 黄金测试：互溶严格度 + 接纳激活（三分 mode=all）。

用"夏天"真实盘（阿卡比特，日生）验证。断言依据 docs/astrology_reception.md §6。
"""

from datetime import datetime
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import ReceptionEngine, load_knowledge
from shared.enums import DignityState, HouseSystem, Planet
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def chart():
    p = Person(
        id="p_xiatian_reception",
        name="夏天",
        gender="女",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


@pytest.fixture(scope="module")
def engine():
    return ReceptionEngine(load_knowledge())


@pytest.fixture(scope="module")
def positions(chart):
    return {pl: (cp.sign.sign, cp.sign.degree_in_sign) for pl, cp in chart.planets.items()}


def _find_mutual(recs, a, b):
    for r in recs:
        if {r.planet_a, r.planet_b} == {a, b}:
            return r
    return None


def _find_acceptance(accs, acceptor, accepted):
    for a in accs:
        if a.acceptor == acceptor and a.accepted == accepted:
            return a
    return None


def test_mutual_sun_jupiter_domicile(engine, positions, chart):
    """太阳（庙+三分）互溶木星（庙），三合。最强档 DOMICILE。"""
    r = _find_mutual(
        engine.detect(positions, sect=chart.sect, aspects=chart.aspects),
        Planet.SUN, Planet.JUPITER,
    )
    assert r is not None
    assert r.dignity_type == DignityState.DOMICILE
    # 完整尊贵集：一方 [庙+三分]，另一方 [庙]
    all_dign = set(r.dignities_of_a_at_b) | set(r.dignities_of_b_at_a)
    assert all_dign == {DignityState.DOMICILE, DignityState.TRIPLICITY}
    # 互溶带相位：三合（太阳拱木星）
    assert r.aspect_type.value == "trine"
    assert r.aspect_nature == "HARMONIOUS"


def test_mutual_mercury_mars_domicile(engine, positions, chart):
    """水星（庙+三分）互溶火星（庙），命主星与火星。"""
    r = _find_mutual(
        engine.detect(positions, sect=chart.sect, aspects=chart.aspects),
        Planet.MERCURY, Planet.MARS,
    )
    assert r is not None
    assert r.dignity_type == DignityState.DOMICILE
    all_dign = set(r.dignities_of_a_at_b) | set(r.dignities_of_b_at_a)
    assert all_dign == {DignityState.DOMICILE, DignityState.TRIPLICITY}
    # 水火相距 66.8°，六合(60°)偏差 6.8° ≤ 六合容差 7°（主流做法）→ 六合
    assert r.aspect_type.value == "sextile"
    assert r.aspect_nature == "HARMONIOUS"


def test_acceptance_mars_receives_sun_dynamic(engine, positions, chart):
    """火星接纳太阳：三分+面 · 刑 · 动态。"""
    a = _find_acceptance(
        engine.detect_acceptance(positions, chart.aspects, sect=chart.sect),
        Planet.MARS, Planet.SUN,
    )
    assert a is not None
    assert a.dignity_type == DignityState.TRIPLICITY
    assert set(a.dignities) == {DignityState.TRIPLICITY, DignityState.FACE}
    assert a.aspect_nature == "DYNAMIC"


def test_acceptance_jupiter_receives_moon_harmonious(engine, positions, chart):
    """木星接纳月亮：三分+面 · 六合 · 和谐。"""
    a = _find_acceptance(
        engine.detect_acceptance(positions, chart.aspects, sect=chart.sect),
        Planet.JUPITER, Planet.MOON,
    )
    assert a is not None
    assert a.dignity_type == DignityState.TRIPLICITY
    assert set(a.dignities) == {DignityState.TRIPLICITY, DignityState.FACE}
    assert a.aspect_nature == "HARMONIOUS"


def test_acceptance_saturn_receives_jupiter_dynamic(engine, positions, chart):
    """土星接纳木星：三分+面 · 对冲 · 动态（木土冲的接纳版）。"""
    a = _find_acceptance(
        engine.detect_acceptance(positions, chart.aspects, sect=chart.sect),
        Planet.SATURN, Planet.JUPITER,
    )
    assert a is not None
    assert set(a.dignities) == {DignityState.TRIPLICITY, DignityState.FACE}
    assert a.aspect_nature == "DYNAMIC"


def test_acceptance_single_weak_dignity_rejected(engine, positions, chart):
    """单个三分/界/面力度不够：非庙/旺时需"有其二"（用户规则，互溶接纳通用）。"""
    accs = engine.detect_acceptance(positions, chart.aspects, sect=chart.sect)
    # 月亮接纳太阳：仅单个三分（六合相位）→ 剔除
    assert _find_acceptance(accs, Planet.MOON, Planet.SUN) is None
    # 太阳接纳火星：仅单个十度（刑相位）→ 剔除
    assert _find_acceptance(accs, Planet.SUN, Planet.MARS) is None
    # 金星接纳土星：仅单个十度（刑相位）→ 剔除
    assert _find_acceptance(accs, Planet.VENUS, Planet.SATURN) is None
    # 严格度下仅保留三项弱尊贵满足"有其二"的接纳
    assert len(accs) == 3


def test_acceptance_requires_aspect(engine, positions, chart):
    """太阳旺接纳水星（白羊·太阳旺），但无激活相位 → 不构成接纳。"""
    a = _find_acceptance(
        engine.detect_acceptance(positions, chart.aspects, sect=chart.sect),
        Planet.SUN, Planet.MERCURY,
    )
    assert a is None


def test_mutual_pair_not_duplicated_in_acceptance(engine, positions, chart):
    """已成互溶的太阳↔木星，不再作为单向接纳重复出现（互溶更强，覆盖之）。"""
    a = _find_acceptance(
        engine.detect_acceptance(positions, chart.aspects, sect=chart.sect),
        Planet.JUPITER, Planet.SUN,
    )
    assert a is None


def test_outer_planets_and_points_excluded(engine, positions, chart):
    """三王星（世代性）与虚点（非行星）不参与互溶/接纳，只做相位落宫叠加。"""
    excluded = {Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
                Planet.NORTH_NODE, Planet.SOUTH_NODE, Planet.CHIRON, Planet.LILITH}
    recs = engine.detect(positions, sect=chart.sect)
    accs = engine.detect_acceptance(positions, chart.aspects, sect=chart.sect)
    for r in recs:
        assert r.planet_a not in excluded and r.planet_b not in excluded
    for a in accs:
        assert a.acceptor not in excluded and a.accepted not in excluded
    # 现代制伪影（土星↔天王互溶）随之消失
    assert _find_mutual(recs, Planet.SATURN, Planet.URANUS) is None
    # 虚点产生的"接纳"（如月亮接纳南交点）消失
    assert _find_acceptance(accs, Planet.MOON, Planet.SOUTH_NODE) is None


def test_strictness_direction_logic(engine):
    """互溶严格度（standard）：庙/旺单一；三分/界/面需有其二。"""
    assert engine._passes_direction([DignityState.TRIPLICITY], "standard") is False
    assert engine._passes_direction([DignityState.TRIPLICITY, DignityState.TERM], "standard") is True
    assert engine._passes_direction([DignityState.DOMICILE], "standard") is True
    # strict：弱尊贵一律不构成互溶
    assert engine._passes_direction([DignityState.TRIPLICITY, DignityState.TERM], "strict") is False
    assert engine._passes_direction([DignityState.DOMICILE], "strict") is True
    # lenient：任何单一都行
    assert engine._passes_direction([DignityState.FACE], "lenient") is True
