"""法达黄金测试：大限/子限计算 + 劫夺宫主 + 时间领主×本命条件解读。

用"夏天"真实盘（昼生）验证。docs/astrology_timing.md §3。
"""

from datetime import datetime, timezone
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from domain.astrology.interpretation import affliction_readings, natal_reading
from domain.timeline.firdaria import compute_firdaria, firdaria_reading, house_rulers, time_lord_character
from shared.enums import FirdariaMethod, HouseSystem, Planet, Sect
from shared.models import BirthData, GeoLocation, Person


def _person(hour: int, minute: int = 0) -> Person:
    return Person(
        id="p_firdaria",
        name="测试",
        birth=BirthData(
            datetime(1991, 3, 21, hour, minute, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def chart():
    return NatalChartCalculator().compute(_person(9, 25))


@pytest.fixture(scope="module")
def kb():
    return load_knowledge()


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def test_firdaria_moon_major_mars_sub(chart):
    """夏天（昼生）@2026-08-04 → 月亮大限 + 火星子限。

    子限 = 大限等分 7 段（宫神星网算法）：月亮大限 9 年 ÷ 7 ≈ 470 天/段。
    宫神星网参考：火星子限 2026-01-27 → 2027-05-12。
    """
    period = compute_firdaria(chart.epoch_utc, chart.sect, REF)
    assert period.major_lord == Planet.MOON
    assert period.sub_lord == Planet.MARS
    # 大限 2022 → 2031
    assert period.major_start.year == 2022
    assert period.major_end.year == 2031
    # 子限含参考日
    assert period.sub_start <= REF <= period.sub_end
    # 火星子限 ≈ 2026-01-27 → 2027-05-12（对齐宫神星网）
    assert abs((period.sub_start - datetime(2026, 1, 27, tzinfo=timezone.utc)).days) <= 2
    assert abs((period.sub_end - datetime(2027, 5, 12, tzinfo=timezone.utc)).days) <= 2
    # 子限跨度 ≈ 大限/7 ≈ 470 天
    days = (period.sub_end - period.sub_start).days
    assert 400 <= days <= 550


def test_firdaria_product_night_nodes_after_mars_and_compatibility():
    """产品默认：夜生火星后接南北交；nodes_at_end 只作为旧口径 compatibility preset。"""
    day_chart = NatalChartCalculator().compute(_person(9, 25))
    assert day_chart.sect == Sect.DAY
    assert compute_firdaria(day_chart.epoch_utc, day_chart.sect, day_chart.epoch_utc).major_lord == Planet.SUN

    night_chart = NatalChartCalculator().compute(_person(22, 0))
    assert night_chart.sect == Sect.NIGHT
    assert compute_firdaria(night_chart.epoch_utc, night_chart.sect, night_chart.epoch_utc).major_lord == Planet.MOON

    age_39 = night_chart.epoch_utc.replace(year=night_chart.epoch_utc.year + 39)
    age_42 = night_chart.epoch_utc.replace(year=night_chart.epoch_utc.year + 42)
    age_44 = night_chart.epoch_utc.replace(year=night_chart.epoch_utc.year + 44)
    assert compute_firdaria(night_chart.epoch_utc, night_chart.sect, age_39).major_lord == Planet.NORTH_NODE
    assert compute_firdaria(night_chart.epoch_utc, night_chart.sect, age_42).major_lord == Planet.SOUTH_NODE
    assert compute_firdaria(night_chart.epoch_utc, night_chart.sect, age_44).major_lord == Planet.SUN

    compat = compute_firdaria(
        night_chart.epoch_utc,
        night_chart.sect,
        age_39,
        method=FirdariaMethod.NODES_AT_END,
    )
    assert compat.major_lord == Planet.SUN

    # 日生 75 年周期（含双交）验证：日生 @ birth+75年 应回到太阳
    late = compute_firdaria(day_chart.epoch_utc, day_chart.sect, day_chart.epoch_utc.replace(year=day_chart.epoch_utc.year + 75))
    assert late.major_lord == Planet.SUN


def test_firdaria_node_major_is_whole_node_period():
    """节点大限读整段南/北交主题，不再机械切成 7 个行星子限。"""
    night_chart = NatalChartCalculator().compute(_person(22, 0))
    north_ref = night_chart.epoch_utc.replace(year=night_chart.epoch_utc.year + 40)
    north = compute_firdaria(night_chart.epoch_utc, night_chart.sect, north_ref)
    assert north.major_lord == Planet.NORTH_NODE
    assert north.sub_lord == Planet.NORTH_NODE
    assert north.sub_start == north.major_start
    assert north.sub_end == north.major_end

    south_ref = night_chart.epoch_utc.replace(year=night_chart.epoch_utc.year + 43)
    south = compute_firdaria(night_chart.epoch_utc, night_chart.sect, south_ref)
    assert south.major_lord == Planet.SOUTH_NODE
    assert south.sub_lord == Planet.SOUTH_NODE
    assert south.sub_start == south.major_start
    assert south.sub_end == south.major_end


def test_house_rulers_including_intercepted(chart, kb):
    """劫夺宫主：6宫 [金星,火星]（天秤+劫夺天蝎），12宫 [火星,金星]（白羊+劫夺金牛）。"""
    assert set(house_rulers(chart, kb, 6)) == {Planet.VENUS, Planet.MARS}
    assert set(house_rulers(chart, kb, 12)) == {Planet.MARS, Planet.VENUS}


def test_firdaria_reading_time_lord_condition(chart, kb):
    """时间领主×本命条件：火星子限主题覆盖 工作/玄学/技艺（12R+劫夺6R+落1）。"""
    reading = firdaria_reading(chart, kb, REF)
    assert reading.major  # 大限主题非空（月亮：3宫沟通 + 1宫自我）
    sub_words = [i.word for i in reading.sub]
    assert any("工作" in w or "技艺" in w or "玄学" in w for w in sub_words)
    # 火星管辖宫（12/6）进入解读
    assert any("12宫" in ev or "6宫" in ev for i in reading.sub for ev in i.evidence)


# -- 子限行为类型（经验库） -------------------------------------------------

def test_mars_sub_character_paid_investment(chart, kb):
    """火星子限：凶/费力 + 落2宫财帛 → 花钱投入、硬干（对应"报班花钱学习"）。"""
    ch = time_lord_character(chart, kb, Planet.MARS)
    assert ch.nature == "malefic"
    assert "费力" in ch.tone
    # 火星末度入2宫 → 领域含财帛/花钱
    assert any("财帛" in d or "花钱" in d for d in ch.domains)
    # 受克 → 过程费力
    assert "费力" in ch.effort
    # 行为特征含行动/投入
    assert any("投入" in b or "硬干" in b for b in ch.behavior)


def test_jupiter_sub_character_free_study(chart, kb):
    """木星子限：吉/宽松 + 落3宫学习 → 免费自学、搜集（对应"搜集网课自学"）。"""
    ch = time_lord_character(chart, kb, Planet.JUPITER)
    assert ch.nature == "benefic"
    assert "宽松" in ch.tone
    # 木星落3宫 → 领域含学习/课程
    assert any("学习" in d or "课程" in d for d in ch.domains)
    # 吉星 → 较顺
    assert "较顺" in ch.effort
    assert any("搜集" in b or "学习" in b for b in ch.behavior)


def test_mars_affliction_noble_received(chart, kb):
    """火星刑太阳（有接纳）+ 太阳主贵 → "费力上升"，不概论凶。"""
    affs = affliction_readings(chart, kb, Planet.MARS)
    noble = [a for a in affs if a.target_kind == "noble"]
    assert any(a.received and a.label == "费力上升" for a in noble)
    # 世代/虚点（北交/莉莉丝）的克 → 外部压力
    outer = [a for a in affs if a.target_kind == "outer"]
    assert any(a.label == "外部压力" for a in outer)


def test_composite_export_json_friendly(chart, kb):
    """出口：法达/本命/月返复合模型 to_dict 全 JSON 友好。"""
    import json

    d = firdaria_reading(chart, kb, REF).to_dict()
    json.dumps(d, ensure_ascii=False)
    assert d["period"]["sub_lord"] == "mars"
    assert "sub_character" in d and d["sub_character"]["effort"]

    nd = natal_reading(chart, kb).to_dict()
    json.dumps(nd, ensure_ascii=False)
    assert nd["domains"]["career"]
