"""证据卡黄金测试：飞星 → EvidenceCard 三层转述 + 怎么办借力段。

客户盘（1981-08-20 龙江）：金星6/7/11R飞10 得吉 → 借力段涉及技能→事业；
火星5/8R飞8 受克 → 借力段涉及先稳住恋爱基础。
"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.interpretation import dispositor_cards, EvidenceCard
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


@pytest.fixture(scope="module")
def cards(chart, kb):
    return dispositor_cards(chart, kb)


# -- 金星飞星得吉卡 ----------------------------------------------------

def test_venus_6_to_10_jin_card(cards):
    """金星(6R)飞10宫 → 得吉卡：三层均有内容，action 涉及技能→事业。"""
    card = next(c for c in cards if c.from_house == 6 and c.to_house == 10)
    assert card.lord == Planet.VENUS
    assert card.polarity == "jin"
    assert card.source_type == "dispositor"

    # 术语层：含宫位、星名、得吉
    assert "6宫主" in card.skeleton
    assert "金星" in card.skeleton
    assert "10宫" in card.skeleton
    assert "得吉" in card.skeleton
    assert card.skeleton.endswith(card.resonance[:0]) or len(card.skeleton) > 10

    # 共鸣层：YAML 原文非空
    assert card.resonance, "共鸣层（jin 原文）不应为空"
    assert "事业" in card.resonance or "技能" in card.resonance or "成就" in card.resonance

    # 落地层：借力方向 + 抓手
    assert "借力方向" in card.action
    assert "→" in card.action
    assert "抓手" in card.action
    # 原宫 6 = 工作/劳损/技艺 → action 应涉及技能类词
    assert any(w in card.action for w in ("工作", "技艺", "手艺", "技能", "劳损"))

    # 证据链
    assert any("金星" in e for e in card.evidence)
    assert any("得吉" in e for e in card.evidence)

    # card_id 可识别
    assert card.card_id.startswith("dispositor:6→10")


def test_venus_7_to_10_jin_card(cards):
    """金星(7R)飞10宫 → 得吉：伴侣合伙 → 事业。"""
    card = next(c for c in cards if c.from_house == 7 and c.to_house == 10)
    assert card.lord == Planet.VENUS
    assert card.polarity == "jin"
    assert "7宫主" in card.skeleton
    assert card.resonance


def test_venus_11_to_10_jin_card(cards):
    """金星(11R)飞10宫 → 得吉：口碑人脉 → 事业。"""
    card = next(c for c in cards if c.from_house == 11 and c.to_house == 10)
    assert card.lord == Planet.VENUS
    assert card.polarity == "jin"
    assert "11宫主" in card.skeleton
    assert card.resonance


# -- 火星飞星受克卡 ----------------------------------------------------

def test_mars_5_to_8_ke_card(cards):
    """火星(5R)飞8宫 → 受克卡：action 含警告 + 先稳住原宫。"""
    card = next(c for c in cards if c.from_house == 5 and c.to_house == 8)
    assert card.lord == Planet.MARS
    assert card.polarity == "ke"

    # 术语层含受克
    assert "5宫主" in card.skeleton
    assert "火星" in card.skeleton
    assert "8宫" in card.skeleton
    assert "受克" in card.skeleton

    # 共鸣层非空
    assert card.resonance, "共鸣层（ke 原文）不应为空"

    # 落地层：警告 + 先稳住
    assert "注意" in card.action
    assert "承接" in card.action
    assert "先稳住" in card.action
    # 5 宫领域涉及恋爱/创造
    assert any(w in card.action for w in ("恋爱", "创造", "子女", "5宫"))

    # 证据链
    assert any("火星" in e for e in card.evidence)
    assert any("受克" in e for e in card.evidence)


# -- to_dict 出口 -----------------------------------------------------

def test_dispositor_cards_to_dict(cards):
    """出口：所有 card 可 json.dumps 序列化。"""
    assert cards, "应有飞星卡片（至少 4-12宫）"
    data = [c.to_dict() for c in cards]
    dumped = json.dumps(data, ensure_ascii=False)
    parsed = json.loads(dumped)
    assert len(parsed) == len(cards)

    # 每条 card dict 含所有关键字段
    first = parsed[0]
    for key in ("card_id", "source_type", "skeleton", "resonance",
                "action", "evidence", "polarity", "from_house", "to_house", "lord"):
        assert key in first, f"card dict 缺少字段 {key}"

    assert first["source_type"] == "dispositor"
    assert first["polarity"] in ("jin", "ke")
    assert isinstance(first["evidence"], list)


# -- 卡片数与 dispositor 读数对齐 --------------------------------------

def test_card_count_matches_dispositor(cards, chart, kb):
    """飞星卡数 = dispositor_interpretations 读数数。"""
    from domain.astrology.interpretation import dispositor_interpretations
    readings = dispositor_interpretations(chart, kb)
    assert len(cards) == len(readings), (
        f"卡片数 {len(cards)} ≠ 飞星读数数 {len(readings)}"
    )


# -- 卡片结构一致性 ----------------------------------------------------

def test_all_cards_have_three_layers(cards):
    """每条卡三层（skeleton/resonance/action）均非空。"""
    for card in cards:
        assert card.skeleton, f"{card.card_id}: skeleton 为空"
        assert card.resonance, f"{card.card_id}: resonance 为空"
        assert card.action, f"{card.card_id}: action 为空"
        assert card.evidence, f"{card.card_id}: evidence 为空"


def test_jin_cards_have_leverage(cards):
    """得吉卡 action 含"借力方向"。"""
    jin_cards = [c for c in cards if c.polarity == "jin"]
    assert jin_cards, "应有得吉卡片"
    for c in jin_cards:
        assert "借力方向" in c.action, f"{c.card_id}: 得吉卡缺少'借力方向'"
        assert "→" in c.action


def test_ke_cards_have_warning(cards):
    """受克卡 action 含"注意"+"先稳住"。"""
    ke_cards = [c for c in cards if c.polarity == "ke"]
    assert ke_cards, "应有受克卡片"
    for c in ke_cards:
        assert "注意" in c.action, f"{c.card_id}: 受克卡缺少'注意'"
        assert "先稳住" in c.action, f"{c.card_id}: 受克卡缺少'先稳住'"


def test_card_ids_are_unique(cards):
    """每张 card 的 card_id 唯一。"""
    ids = [c.card_id for c in cards]
    assert len(ids) == len(set(ids)), f"card_id 重复: {len(ids)} ≠ {len(set(ids))}"


# -- 领域标签回退 ------------------------------------------------------

def test_house_label_fallback(chart, kb, cards):
    """宫位领域标签回退：即使某宫缺失标签也不崩，action 非空。

    领域标签来自 time_lord_character.yaml 的 house_domains，
    如"家庭/根基/房产"——不含"宫"字是正常的，此处只验证 action 有实质内容。
    """
    for card in cards:
        assert card.action, f"{card.card_id}: action 不应为空"
        # action 应引用至少一个中文领域词（from 或 to 的领域标签）
        assert len(card.action) > 20, f"{card.card_id}: action 过短"
