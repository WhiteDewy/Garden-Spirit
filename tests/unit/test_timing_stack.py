"""时机栈合成黄金测试：一次调用出"当前时期"（法达+返回盘+推运+行运）。

夏天 @ 2026-08-04。docs/astrology_timing.md。
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.common import house_lord
from domain.astrology.knowledge import load_knowledge
from domain.timeline import build_timing_stack
from shared.enums import AspectType, DignityState, HouseSystem, Planet
from shared.models import BirthData, ChartAcceptance, GeoLocation, Person


@pytest.fixture(scope="module")
def person():
    return Person(
        id="p_xiatian_stack",
        name="夏天",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def chart(person):
    return NatalChartCalculator().compute(person)


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def test_timing_stack_all_layers(person, chart):
    """合成：法达+日返+月返+次限+三限+行运 六层齐全。"""
    ts = build_timing_stack(person, chart, load_knowledge(), reference=REF)
    # 法达：月亮大限 + 火星子限
    assert ts.firdaria.period.major_lord.value == "moon"
    assert ts.firdaria.period.sub_lord.value == "mars"
    # 次限月亮：处女4宫（对齐宫神星网）
    assert ts.progressed_moon.sign.value == "virgo"
    assert ts.progressed_moon.natal_house == 4
    # 三限月亮有值
    assert ts.tertiary_moon.sign is not None
    # 行运窗口非空且含参考月
    assert ts.transits
    assert ts.transits[0]["month"] == "2026-08"


def test_timing_stack_export_exposes_helper_targets(person, chart):
    """时机栈导出直接目标、帮手目标、实际扫描目标三层，便于前端审计。"""
    chart = deepcopy(chart)
    chart.receptions = []
    chart.acceptances = [ChartAcceptance(
        acceptor=Planet.JUPITER,
        accepted=Planet.MARS,
        dignities=(DignityState.TRIPLICITY,),
        dignity_type=DignityState.TRIPLICITY,
        score=3,
        aspect_type=AspectType.TRINE,
        aspect_nature="HARMONIOUS",
        description_zh="木星接纳火星",
    )]
    d = build_timing_stack(person, chart, load_knowledge(), reference=REF).to_dict()
    assert set(d["transit_targets"]) == {"moon", "mars"}
    assert "jupiter" in d["helper_transit_targets"]
    assert set(d["helper_transit_targets"]).isdisjoint(d["transit_targets"])
    assert set(d["scoring_transit_targets"]) == set(d["transit_targets"]) | set(d["helper_transit_targets"])
    first = d["transits"][0]
    assert first["target_planets"] == d["transit_targets"]
    assert first["helper_target_planets"] == d["helper_transit_targets"]
    assert first["scoring_target_planets"] == d["scoring_transit_targets"]


def test_timing_stack_uses_question_significators_from_enrichment(person, chart):
    """阶段5：时机栈不能只看法达领主，也要吃本轮问题的真实承载者。"""
    kb = load_knowledge()
    career_lord = house_lord(chart, kb, 10)

    d = build_timing_stack(
        person,
        chart,
        kb,
        reference=REF,
        enrichment={"focus_planets": ["venus"], "focus_house_lords": [10]},
    ).to_dict()

    assert set(d["transit_targets"]).issuperset({"moon", "mars", "venus", career_lord.value})
    assert "year_lord" not in d
    assert d["transits"][0]["target_planets"] == d["transit_targets"]
    assert set(d["scoring_transit_targets"]).issuperset(d["transit_targets"])


def test_timing_stack_export(person, chart):
    """出口：to_dict 全 JSON 友好，含法达权威 + 五层。"""
    d = build_timing_stack(person, chart, load_knowledge(), reference=REF).to_dict()
    json.dumps(d, ensure_ascii=False)
    assert d["type"] == "timing_stack"
    assert d["timing_authority"] == "firdaria"
    assert "firdaria" in d and "solar_return" in d and "lunar_return" in d
    assert "progressed_moon" in d and "tertiary_moon" in d and "transits" in d
    assert d["firdaria"]["period"]["major_lord"] == "moon"
    assert d["firdaria"]["period"]["sub_lord"] == "mars"
    assert set(d["transit_targets"]) == {"moon", "mars"}
    assert "year_lord" not in d
