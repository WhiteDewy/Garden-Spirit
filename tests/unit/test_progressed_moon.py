"""次限月亮黄金测试：1天=1年，星座+本命落宫+换座时间。

夏天本命（月亮双子1.07°）@ 2026-08-04（35.4岁）。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline import ProgressedMoonCalculator
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def natal():
    p = Person(
        id="p_xiatian_pm",
        name="夏天",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def test_progressed_moon_summer(natal):
    """次限月亮：处女 ~23.9° 落本命4宫（整宫定位，对齐宫神星网），2027-01 换天秤。"""
    pm = ProgressedMoonCalculator().compute(natal, natal.epoch_utc.replace(tzinfo=timezone.utc), REF)
    assert pm.sign.value == "virgo"
    assert 23.0 <= pm.degree_in_sign <= 24.5
    # 太阳弧法次限盘+阿卡比特（宫神星网参考：处女23°56′落4宫，次限上升巨蟹5°）
    assert pm.natal_house == 4
    assert pm.next_sign.value == "libra"
    # 换座时间合理：已入座早于参考日，下次换座晚于参考日
    assert pm.entered_sign_date <= REF
    assert pm.next_sign_change_date > REF


def test_progressed_moon_progression_rule(natal):
    """次限规则：次限日期 = 出生 + 年龄(天)，年龄~35.4。"""
    pm = ProgressedMoonCalculator().compute(natal, natal.epoch_utc.replace(tzinfo=timezone.utc), REF)
    assert 35.0 <= pm.age_years <= 36.0
    assert pm.progressed_date.date().year == 1991  # 出生后 ~35 天


def test_progressed_moon_export(natal):
    """出口：to_dict 全 JSON 友好。"""
    pm = ProgressedMoonCalculator().compute(natal, natal.epoch_utc.replace(tzinfo=timezone.utc), REF)
    d = pm.to_dict()
    json.dumps(d, ensure_ascii=False)
    assert d["type"] == "progressed_moon"
    assert d["lens"]  # 情绪透镜非空
