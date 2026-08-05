"""日返黄金测试：太阳回到本命黄经 + 当前地排盘 + 出口。

夏天本命（太阳双鱼29.9°）+ 当前地杭州富阳 + 参考 2026-08-04。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline import SolarReturnCalculator
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def natal():
    p = Person(
        id="p_xiatian_sr",
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
    # 日返盘地点 = 出生地（宫神星网参考：6宫头白羊2°55′，土星6宫）
    return GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川")


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def test_solar_return_current_year(natal, location):
    """当前生效日返 = 参考时刻之前最近一次（2026-03-20，管一整年）。"""
    sr = SolarReturnCalculator().compute(natal, location, REF)
    tz = zoneinfo.ZoneInfo("Asia/Shanghai")
    assert sr.moment.astimezone(tz).date().isoformat() == "2026-03-20"
    assert sr.effective_until.astimezone(tz).date().isoformat() == "2027-03-21"
    assert sr.moment <= REF <= sr.effective_until


def test_solar_return_5th_and_6th_houses(natal, location):
    """出生地+阿卡比特：5宫群星（日水火星海王）无土星；土星落6宫（白羊）。"""
    d = sr_dict(natal, location)
    assert d["sun_house"] == 5
    assert d["ascendant_sign"] == "scorpio"
    # 5宫 = 太阳+水星+火星+海王（无土星）
    assert {"sun", "mercury", "mars", "neptune"} <= set(d["houses"]["5"])
    assert "saturn" not in d["houses"]["5"]
    # 6宫 = 月亮+金星+土星（对齐宫神星网参考）
    assert "saturn" in d["houses"]["6"]
    assert d["moon_house"] == 6
    # 6宫头白羊（≈2°55′）
    assert d["ascendant_sign"] == "scorpio"


def test_solar_return_export_json(natal, location):
    """出口：日返 to_dict 全 JSON 友好。"""
    d = sr_dict(natal, location)
    json.dumps(d, ensure_ascii=False)
    assert d["type"] == "solar_return"
    assert d["location"] == "山西陵川"


def test_solar_return_default_birth_place(natal, location):
    """默认用出生地：不传 location、只传 birth_location → birth_place（留 tag 后期可改）。"""
    calc = SolarReturnCalculator()
    sr = calc.compute(natal, birth_location=location, reference=REF)
    d = sr.to_dict()
    assert d["location"] == "山西陵川"
    assert d["location_type"] == "birth_place"
    # 与显式出生地结果一致
    sr2 = calc.compute(natal, location=location, birth_location=location, reference=REF)
    assert sr2.to_dict()["houses"] == d["houses"]


def test_solar_return_location_type(natal, location):
    """地点标注：出生地排盘→birth_place，当前地排盘→current_place。"""
    calc = SolarReturnCalculator()
    sr_birth = calc.compute(natal, location, REF, birth_location=location)
    assert sr_birth.to_dict()["location_type"] == "birth_place"

    current = GeoLocation(30.05, 119.96, timezone_name="Asia/Shanghai", place_name="杭州富阳")
    sr_current = calc.compute(natal, current, REF, birth_location=location)
    assert sr_current.to_dict()["location_type"] == "current_place"


def sr_dict(natal, location):
    sr = SolarReturnCalculator().compute(natal, location, REF)
    return sr.to_dict()
