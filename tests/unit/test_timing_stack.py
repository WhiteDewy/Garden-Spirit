"""时机栈合成黄金测试：一次调用出"当前时期"（法达+返回盘+推运+行运）。

夏天 @ 2026-08-04。docs/astrology_timing.md。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from domain.timeline import build_timing_stack
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person


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


def test_timing_stack_export(person, chart):
    """出口：to_dict 全 JSON 友好，含六层。"""
    d = build_timing_stack(person, chart, load_knowledge(), reference=REF).to_dict()
    json.dumps(d, ensure_ascii=False)
    assert d["type"] == "timing_stack"
    assert "firdaria" in d and "solar_return" in d and "lunar_return" in d
    assert "progressed_moon" in d and "tertiary_moon" in d and "transits" in d
    assert d["year_lord"] == "mars"
