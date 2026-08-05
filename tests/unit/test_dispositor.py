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
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, GeoLocation, Person


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


def test_dispositor_export(chart, kb):
    """出口：to_dict 全 JSON 友好。"""
    readings = dispositor_interpretations(chart, kb)
    assert readings
    d = [r.to_dict() for r in readings]
    json.dumps(d, ensure_ascii=False)
    assert d[0]["from_house"] and d[0]["quality"] in ("jin", "ke")
