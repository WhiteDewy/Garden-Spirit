"""解释引擎黄金测试：语义场域过滤 + 结构调制 + 事件门槛 + 宫位交感 + 连接分级 + 末度。

用"夏天"真实盘（阿卡比特）验证引擎的通用性（技法通用，盘只作夹具）。
"""

from datetime import datetime
import zoneinfo

import pytest

from domain.astrology.interpretation import (
    ConnectionClassifier,
    HouseSignificationEngine,
    detect_synapsis,
    natal_reading,
)
from domain.astrology.interpretation.synapsis import effective_house
from domain.astrology.knowledge import load_knowledge
from domain.astrology.calculation import NatalChartCalculator
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def chart():
    p = Person(
        id="p_xiatian_interp",
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
def kb():
    return load_knowledge()


@pytest.fixture(scope="module")
def engine(kb):
    return HouseSignificationEngine(kb)


@pytest.fixture(scope="module")
def classifier(kb):
    return ConnectionClassifier(kb)


# -- 末度 ------------------------------------------------------------------

def test_effective_house_mars_crosses_2nd(chart):
    """火星双子23.3°，2宫头双子23.5°，距0.2° → 末度入2。"""
    assert effective_house(chart, Planet.MARS) == 2


# -- 语义场域过滤（同一个12宫，不同问题域激活不同含义） -------------------

def test_12th_wealth_domain_activates_money_not_small_person(chart, engine):
    items = engine.interpret(chart, "wealth", houses=[12])
    words = [i.word for i in items]
    assert any("玄学" in w or "暗财" in w for w in words)
    assert not any("小人" in w for w in words)   # 问财不甩小人


def test_12th_relationship_domain_activates_tendency_not_money(chart, engine):
    items = engine.interpret(chart, "relationship", houses=[12])
    words = [i.word for i in items]
    assert any("恋爱脑" in w for w in words)     # 倾向切片默认发射
    assert not any("玄学" in w or "暗财" in w for w in words)  # 问情不甩财


def test_dual_track_good_bad_not_netted(chart, engine):
    """吉凶两论：9宫既有吉轨(深造资质)又有凶轨(考试运差)，各论各的、不抵消。"""
    learning = engine.interpret(chart, "learning", houses=[9])
    words = [i.word for i in learning]
    assert any("深造" in w for w in words)                  # 吉轨：土星庙
    assert any("考试运" in w or "费力" in w for w in words)  # 凶轨：受克
    gaoxue = next(i for i in learning if "深造" in i.word)
    kaoshi = next(i for i in learning if "考试运" in i.word or "费力" in i.word)
    # 各论各的：吉轨证据带"尊贵+8"（土星庙），凶轨证据带"刑"（金星刑土星未接纳）
    assert any("尊贵" in ev and "+" in ev for ev in gaoxue.evidence)
    assert any("刑" in ev for ev in kaoshi.evidence)
    # 共振词不再承诺"学霸"
    assert not any("学霸" in r for r in gaoxue.resonance)


def test_mercury_affliction_drags_learning_houses(chart, engine):
    """水星刑天王/刑海王（三王星无接纳）→ 命主/财帛/恋爱宫（1/2/5）凶分量大于吉。"""
    for house in (1, 2, 5):
        pos, neg, _, neg_ev = engine._house_quality_dual(chart, house)
        assert neg > pos, f"{house}宫凶分量应大于吉分量（水星刑克多）"
        assert any("刑" in ev for ev in neg_ev)  # 凶轨证据带刑克


def test_12th_affliction_mitigated_by_benefic(chart, engine):
    """12R火星受克 → 小人生理（凶轨）；金星庙落12宫 → 恋爱脑/化解（吉轨）。各论各的。"""
    items = engine.interpret(chart, "relationship", houses=[12])
    xiaoren = next((i for i in items if "小人" in i.word), None)
    assert xiaoren is not None          # 火星受克 → 小人倾向存在
    # 凶轨证据：火星凶星/受刑（各论各的，不带吉星）
    assert any("火星为凶星" in ev or "刑" in ev for ev in xiaoren.evidence)
    # 恋爱脑（中性）同带吉凶：金星庙（吉轨）+ 火星受克（凶轨）
    lianai = next((i for i in items if "恋爱脑" in i.word), None)
    assert lianai is not None
    assert any("金星" in ev for ev in lianai.evidence)
    assert any("火星为凶星" in ev for ev in lianai.evidence)


# -- 事件预言门槛 ----------------------------------------------------------

def test_event_three_way_gated_out(chart, engine):
    """三方关系（event，需2强连接收敛）：夏天盘12↔7/8仅弱连接 → 不发射。"""
    items = engine.interpret(chart, "relationship", houses=[12])
    assert not any("三方关系" in i.word for i in items)


# -- 飞行增强与证据 --------------------------------------------------------

def test_flight_evidence_in_wealth_reading(chart, engine):
    """12R火星末度飞2宫 → 玄学财条目带"飞2宫"证据 + 强度增强。"""
    items = engine.interpret(chart, "wealth", houses=[12])
    target = next(i for i in items if "玄学" in i.word)
    assert any("飞2宫" in ev for ev in target.evidence)
    # 玄学财（正向+飞行增强）应排在该域解读前列
    assert target.strength >= 3.5


# -- 宫位交感 --------------------------------------------------------------

def test_synapsis_mercury_1_2_5(chart, kb):
    """水星 = 1R + 2R + 5R（命主/财帛/恋爱）交感宫群。"""
    hubs = {h.hub_planet: h.houses for h in detect_synapsis(chart, kb)}
    assert hubs[Planet.MERCURY] == (1, 2, 5)


def test_synapsis_jupiter_7_8_11(chart, kb):
    """木星 = 7R + 8R + 11R（伴侣/亲密共享/社群）交感宫群。"""
    hubs = {h.hub_planet: h.houses for h in detect_synapsis(chart, kb)}
    assert hubs[Planet.JUPITER] == (7, 8, 11)


# -- 连接分级 --------------------------------------------------------------

def test_connection_12_5_mutual_strong(chart, classifier):
    """12↔5：12R火星 ↔ 5R水星 庙互溶（强）。"""
    conns = classifier.classify(chart, 12, 5)
    assert any(c.conn_type == "reception_mutual" and classifier.is_strong(c) for c in conns)


def test_connection_12_7_latent_weak(chart, classifier):
    """12↔7：7R木星对12R火星仅单向三分尊严、无相位 → 潜在（弱，不达标）。"""
    conns = classifier.classify(chart, 12, 7)
    assert not any(classifier.is_strong(c) for c in conns)
    assert any(c.conn_type == "reception_latent" for c in conns)


def test_connection_12_2_flight(chart, classifier):
    """12↔2：12R火星末度飞2宫 → 飞宫连接。"""
    conns = classifier.classify(chart, 12, 2)
    assert any(c.conn_type == "flight" for c in conns)


# -- 本命解读组合 ----------------------------------------------------------

def test_natal_reading_multi_domain(chart, kb):
    """跨8域本命解读：各域产出非空，职业/财富/感情各取正确语义切片。"""
    reading = natal_reading(chart, kb)
    assert reading.synapsis  # 至少一个交感宫群
    # 职业域 top 应有"高等学问/深造"（土星9/10宫主，9宫三巨头）
    career_words = [i.word for i in reading.top("career")]
    assert any("高等学问" in w for w in career_words)
    # 财富域 top 应有"玄学/灵性"（12R火星飞2增强）
    wealth_words = [i.word for i in reading.top("wealth")]
    assert any("玄学" in w for w in wealth_words)
    # 感情域主切片应有"伴侣"（7宫；恋爱脑为次级倾向，另测于12宫专项）
    rel_words = [i.word for i in reading.domains["relationship"]]
    assert any("伴侣" in w for w in rel_words)
    # 情绪域应有"潜意识/梦境/灵感"（12宫语义场 emotion 切片）
    emo_words = [i.word for i in reading.top("emotion")]
    assert any("潜意识" in w for w in emo_words)
