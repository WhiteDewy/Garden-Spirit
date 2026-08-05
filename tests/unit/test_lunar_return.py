"""月返黄金测试：正向求最近月返 + 当前地排盘 + 出口序列化。

docs/astrology_lunar_return.md §3。夏天本命 + 当前地杭州富阳。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline import LunarReturnCalculator
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def natal():
    p = Person(
        id="p_xiatian_lr",
        name="夏天",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


@pytest.fixture(scope="module")
def location():
    return GeoLocation(30.05, 119.96, timezone_name="Asia/Shanghai", place_name="杭州富阳")


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def test_lunar_return_current_moment(natal, location):
    """当前生效月返 = 参考时刻之前最近一次（2026-07-11），非未来那次。"""
    lr = LunarReturnCalculator().compute(natal, location, REF)
    assert lr.moment.date().isoformat() == "2026-07-11"
    assert lr.effective_until.date().isoformat() == "2026-08-07"
    assert lr.moment <= REF <= lr.effective_until


def test_lunar_return_moon_house_10(natal, location):
    """月亮+火星+天王落10宫（事业主战场）。"""
    d = lr_dict(natal, location)
    assert d["moon_house"] == 10
    assert d["moon_sign"] == "gemini"
    assert set(d["houses"]["10"]) == {"moon", "mars", "uranus"}
    # 上升在狮子/处女边界（精确时刻决定哪侧）
    assert d["ascendant_sign"] in ("leo", "virgo")


def test_lunar_return_export_json(natal, location):
    """出口：to_dict 全 JSON 友好（enum→str，无 Planet 对象）。"""
    d = lr_dict(natal, location)
    json.dumps(d, ensure_ascii=False)  # 必须可序列化
    assert d["type"] == "lunar_return"
    assert d["location"] == "杭州富阳"
    # 宫位值全是 str
    assert all(isinstance(k, str) and isinstance(v, list) for k, v in d["houses"].items())


def lr_dict(natal, location):
    lr = LunarReturnCalculator().compute(natal, location, REF)
    return lr.to_dict()
